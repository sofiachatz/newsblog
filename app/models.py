from app import app
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
from sqlalchemy import DateTime
from typing import Optional
import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db
from flask_login import UserMixin
from app import login
from time import time
import jwt
import json
from app.search import add_to_index, remove_from_index, query_index
from elasticsearch.exceptions import ConnectionError as ElasticConnectionError
from elasticsearch import ConnectionTimeout   
from app import rq
import redis
from redis import Redis
from rq import Queue
from rq.timeouts import JobTimeoutException
import logging
from redis import RedisError, ConnectionError
from typing import List



redis = Redis()
queue = Queue(connection=redis, default_timeout=600)


class ElasticsearchError(Exception):
    pass

class SearchableMixin(object):

    @classmethod
    def search(cls, expression, page, per_page):
        try:
            ids, total = query_index(cls.__tablename__, expression, page, per_page)
            if total == 0:
                return [], 0
            if total == -1:
                return [], -1
            when = []
            for i in range(len(ids)):
                when.append((ids[i], i))
            query = sa.select(cls).where(cls.id.in_(ids)).order_by(
                db.case(*when, value=cls.id))
            return db.session.scalars(query), total
        except (ElasticConnectionError, ConnectionTimeout):  
            return [], -1  


    @classmethod
    def before_commit(cls, session):
        session._changes = {
            'add': list(session.new),
            'update': list(session.dirty),
            'delete': list(session.deleted)
        }


    @classmethod
    def after_commit(cls, session):
        try:
            for obj in session._changes['add']:
                if isinstance(obj, SearchableMixin):
                    queue.enqueue(add_to_index, obj.__tablename__, obj) 
            for obj in session._changes['update']:
                if isinstance(obj, SearchableMixin):
                    queue.enqueue(add_to_index, obj.__tablename__, obj)
            for obj in session._changes['delete']:
                if isinstance(obj, SearchableMixin):
                    queue.enqueue(remove_from_index, obj.__tablename__, obj) 
            session._changes = None
        except JobTimeoutException as e:
            app.logger.error(f"Job timeout while trying to remove {model} from Elasticsearch: {str(e)}")
            raise JobTimeoutException(f"Job exceeded the maximum timeout of {e.timeout} seconds.")
        except ConnectionError as e:
            app.logger.error(f"Redis connection error: {str(e)}")
            raise e
        except RedisError as e:
            app.logger.error(f"Redis error: {str(e)}")
            raise e

        
    @classmethod
    def reindex(cls):
        try:
            for obj in db.session.scalars(sa.select(cls)):
                queue.enqueue(add_to_index, cls.__tablename__, obj) 
        except ConnectionError as e:
            app.logger.error(f"Redis connection error: {str(e)}")
            raise e
        except RedisError as e:
            app.logger.error(f"Redis error: {str(e)}")
            raise e


db.event.listen(db.session, 'before_commit', SearchableMixin.before_commit)
db.event.listen(db.session, 'after_commit', SearchableMixin.after_commit)



@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))

class User(UserMixin, db.Model): 
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True,
                                                unique=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True,
                                             unique=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    posts: so.Mapped[List['Post']] = so.relationship('Post', back_populates='author')
    about_me: so.Mapped[Optional[str]] = so.mapped_column(sa.String(400))
    last_seen: so.Mapped[Optional[datetime]] = so.mapped_column(
        default=lambda: datetime.now(timezone.utc))
    profile_pic: so.Mapped[Optional[str]] = so.mapped_column(sa.String())
    likes: so.Mapped[List["Like"]] = so.relationship("Like", backref='user')
    liked_posts: so.Mapped[Optional[bool]] = so.mapped_column(unique=False, default=False)
    comments: so.Mapped[List["Comment"]] = so.relationship("Comment", back_populates='author')
    likes_comments: so.Mapped[List["Like_Comment"]] = so.relationship("Like_Comment", backref='user')
    last_notification_read_time: so.Mapped[Optional[datetime]]
    notifications_sent: so.Mapped[List["Notification"]] = so.relationship("Notification", foreign_keys='Notification.sender_id', back_populates='sender', primaryjoin='Notification.sender_id == User.id')
    notifications_received: so.Mapped[List["Notification"]] = so.relationship("Notification", foreign_keys='Notification.recipient_id', back_populates='recipient', primaryjoin='Notification.recipient_id == User.id', cascade='all, delete-orphan')
    notification_calls: so.Mapped[List["Notification_Call"]] = so.relationship("Notification_Call", back_populates='user', cascade="all, delete-orphan")

    def unread_notification_count(self):
        last_read_time = self.last_notification_read_time or datetime(1900, 1, 1)
        query = sa.select(Notification).where(Notification.recipient == self,
                                         Notification.timestamp > last_read_time)
        return db.session.scalar(sa.select(sa.func.count()).select_from(
            query.subquery()))

    def add_notification_call(self, name, data):
        db.session.query(Notification_Call).filter_by(user_id=self.id, name=name).delete()
        n = Notification_Call(name=name, payload_json=json.dumps(data), user=self)
        db.session.add(n)
        return n

    def __repr__(self):
        return '<User {}>'.format(self.username)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
            {'reset_password': self.id, 'exp': time() + expires_in},
            app.config['SECRET_KEY'], algorithm='HS256')
    
    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(token, app.config['SECRET_KEY'],
                            algorithms=['HS256'])['reset_password']
        except:
            return
        return db.session.get(User, id)


        

class Post(SearchableMixin, db.Model):
    __searchable__ = ['title','lead_in','body']
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    title: so.Mapped[str] = so.mapped_column(sa.String(140))
    lead_in: so.Mapped[Optional[str]] = so.mapped_column(sa.String(400))
    body: so.Mapped[str] = so.mapped_column(sa.String(7000))
    timestamp: so.Mapped[datetime] = so.mapped_column(
        index=True, default=lambda: datetime.now(timezone.utc))
    user_id: so.Mapped[Optional[int]] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    author: so.Mapped[List['User']] = so.relationship('User', back_populates='posts')
    username: so.Mapped[str] = so.mapped_column(sa.String(64))
    news: so.Mapped[Optional[int]] = so.mapped_column(sa.Integer())
    media: so.Mapped[Optional[int]] = so.mapped_column(sa.Integer())
    showbiz: so.Mapped[Optional[int]] = so.mapped_column(sa.Integer())
    sports: so.Mapped[Optional[int]] = so.mapped_column(sa.Integer())
    viral: so.Mapped[Optional[int]] = so.mapped_column(sa.Integer())
    post_pic: so.Mapped[Optional[str]] = so.mapped_column(sa.String())
    likes: so.Mapped[List["Like"]] = so.relationship("Like", backref="post", cascade="all, delete-orphan")
    comments: so.Mapped[List["Comment"]] = so.relationship("Comment", backref="post", cascade="all, delete-orphan")
    notifications: so.Mapped[List["Notification"]] = so.relationship("Notification", foreign_keys='Notification.post_id', back_populates='post', cascade='all, delete-orphan')

    def __repr__(self):
        return '<Post {}>'.format(self.title)

class Like(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    user_id: so.Mapped[Optional[int]] = so.mapped_column(sa.ForeignKey(User.id))
    post_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(Post.id, ondelete="CASCADE"), nullable=False, index=True)
    timestamp: so.Mapped[datetime] = so.mapped_column(
        index=True, default=lambda: datetime.now(timezone.utc))



class Comment(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    body: so.Mapped[str] = so.mapped_column(sa.String(200))
    user_id: so.Mapped[Optional[int]] = so.mapped_column(sa.ForeignKey(User.id))
    author: so.Mapped[List['User']] = so.relationship('User', back_populates='comments')
    username: so.Mapped[str] = so.mapped_column(sa.String(64))
    post_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(Post.id, ondelete="CASCADE"), nullable=False, index=True)
    timestamp: so.Mapped[datetime] = so.mapped_column(
        index=True, default=lambda: datetime.now(timezone.utc))
    parent_id: so.Mapped[Optional[int]] = so.mapped_column(sa.ForeignKey('comment.id', ondelete="CASCADE"), nullable=True)
    replies: so.Mapped[List["Comment"]] = so.relationship("Comment", backref=db.backref('parent', remote_side=[id]), lazy='dynamic', cascade='all, delete')
    reply_to: so.Mapped[Optional[int]] = so.mapped_column(sa.Integer())
    likes: so.Mapped[List["Like_Comment"]] = so.relationship("Like_Comment", backref="comment", cascade="all, delete-orphan")
    num_likes: so.Mapped[Optional[int]] = so.mapped_column(sa.Integer(), default=0)
    notifications: so.Mapped[List["Notification"]] = so.relationship("Notification", foreign_keys='Notification.comment_id', back_populates='comment', cascade='all, delete')
    notifications_replies: so.Mapped[List["Notification"]] = so.relationship("Notification", foreign_keys='Notification.reply_comment_id', back_populates='reply_comment', cascade='all, delete')


class Like_Comment(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    user_id: so.Mapped[Optional[int]] = so.mapped_column(sa.ForeignKey(User.id))
    comment_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(Comment.id, ondelete="CASCADE"), nullable=False, index=True)
    timestamp: so.Mapped[datetime] = so.mapped_column(
        index=True, default=lambda: datetime.now(timezone.utc))


class Notification(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    recipient_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id, ondelete="CASCADE"), nullable=False, index=True)
    sender_id: so.Mapped[Optional[int]] = so.mapped_column(sa.ForeignKey(User.id))
    username: so.Mapped[str] = so.mapped_column(sa.String(64))
    post_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(Post.id, ondelete="CASCADE"), nullable=False, index=True)
    comment_id: so.Mapped[Optional[int]] = so.mapped_column(sa.ForeignKey(Comment.id, ondelete="CASCADE"), nullable=True, index=True)
    reply_comment_id: so.Mapped[Optional[int]] = so.mapped_column(sa.ForeignKey(Comment.id, ondelete="CASCADE"), nullable=True, index=True)
    timestamp: so.Mapped[datetime] = so.mapped_column(index=True, default=lambda: datetime.now(timezone.utc))
    category: so.Mapped[str] = so.mapped_column(sa.String(15))
    status: so.Mapped[Optional[bool]] = so.mapped_column(unique=False, default=False)
    status_changed_at: so.Mapped[Optional[datetime]] = so.mapped_column(DateTime(timezone=True), nullable=True)
    sender: so.Mapped[User] = so.relationship(foreign_keys=[sender_id], back_populates='notifications_sent', primaryjoin='Notification.sender_id == User.id')
    recipient: so.Mapped[User] = so.relationship(foreign_keys=[recipient_id], back_populates='notifications_received', primaryjoin='Notification.recipient_id == User.id')
    post: so.Mapped[Post] = so.relationship(foreign_keys=[post_id], back_populates='notifications')
    comment: so.Mapped[Comment] = so.relationship(foreign_keys=[comment_id], back_populates='notifications')
    reply_comment: so.Mapped[Comment] = so.relationship(foreign_keys=[reply_comment_id], back_populates='notifications_replies')



class Notification_Call(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(128), index=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id, ondelete="CASCADE"), nullable=False, index=True)
    timestamp: so.Mapped[float] = so.mapped_column(index=True, default=time)
    payload_json: so.Mapped[str] = so.mapped_column(sa.Text)

    user: so.Mapped[User] = so.relationship(back_populates='notification_calls')

    def get_data(self):
        return json.loads(str(self.payload_json))
