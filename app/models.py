from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
from typing import Optional
import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db
from flask_login import UserMixin
from app import login
from time import time
import jwt
from app import app
from app.search import add_to_index, remove_from_index, query_index
from elasticsearch.exceptions import ConnectionError as ElasticConnectionError




class SearchableMixin(object):
    @classmethod
    def search(cls, expression, page, per_page):
        try:
            ids, total = query_index(cls.__tablename__, expression, page, per_page)
            if total == 0:
                return [], 0
            when = []
            for i in range(len(ids)):
                when.append((ids[i], i))
            query = sa.select(cls).where(cls.id.in_(ids)).order_by(
                db.case(*when, value=cls.id))
            return db.session.scalars(query), total
        except ElasticConnectionError:
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
        for obj in session._changes['add']:
            if isinstance(obj, SearchableMixin):
                add_to_index(obj.__tablename__, obj)
        for obj in session._changes['update']:
            if isinstance(obj, SearchableMixin):
                add_to_index(obj.__tablename__, obj)
        for obj in session._changes['delete']:
            if isinstance(obj, SearchableMixin):
                remove_from_index(obj.__tablename__, obj)
        session._changes = None

    @classmethod
    def reindex(cls):
        for obj in db.session.scalars(sa.select(cls)):
            add_to_index(cls.__tablename__, obj)
       

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
    posts: so.WriteOnlyMapped['Post'] = so.relationship(
        back_populates='author')
    about_me: so.Mapped[Optional[str]] = so.mapped_column(sa.String(400))
    last_seen: so.Mapped[Optional[datetime]] = so.mapped_column(
        default=lambda: datetime.now(timezone.utc))
    profile_pic: so.Mapped[Optional[str]] = so.mapped_column(sa.String())
    likes = db.relationship('Like', backref='user', passive_deletes=True)
    liked_posts: so.Mapped[Optional[bool]] = so.mapped_column(unique=False, default=False)
    comments = db.relationship('Comment', back_populates='author', passive_deletes=True)
    likes_comments = db.relationship('Like_Comment', backref='user', passive_deletes=True)
    

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
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id),
                                             index=True)
    author: so.Mapped[User] = so.relationship(back_populates='posts')
    news: so.Mapped[Optional[int]] = so.mapped_column(sa.Integer())
    media: so.Mapped[Optional[int]] = so.mapped_column(sa.Integer())
    showbiz: so.Mapped[Optional[int]] = so.mapped_column(sa.Integer())
    sports: so.Mapped[Optional[int]] = so.mapped_column(sa.Integer())
    viral: so.Mapped[Optional[int]] = so.mapped_column(sa.Integer())
    post_pic: so.Mapped[Optional[str]] = so.mapped_column(sa.String())
    likes = db.relationship('Like', backref='post', passive_deletes=True)
    comments = db.relationship('Comment', backref='post', passive_deletes=True)


    def __repr__(self):
        return '<Post {}>'.format(self.title)

class Like(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id, ondelete="CASCADE"), nullable=False)
    post_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(Post.id, ondelete="CASCADE"), nullable=False)
    timestamp: so.Mapped[datetime] = so.mapped_column(
        index=True, default=lambda: datetime.now(timezone.utc))



class Comment(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    body: so.Mapped[str] = so.mapped_column(sa.String(200))
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id, ondelete="CASCADE"), nullable=False)
    post_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(Post.id, ondelete="CASCADE"), nullable=False)
    timestamp: so.Mapped[datetime] = so.mapped_column(
        index=True, default=lambda: datetime.now(timezone.utc))
    parent_id: so.Mapped[Optional[int]] = so.mapped_column(sa.ForeignKey('comment.id', ondelete="CASCADE"), nullable=True)
    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy='dynamic', passive_deletes=True)
    reply_to: so.Mapped[Optional[str]] = so.mapped_column(sa.String(64))
    author: so.Mapped[User] = so.relationship(back_populates='comments')
    likes = db.relationship('Like_Comment', backref='comment', passive_deletes=True)
    num_likes: so.Mapped[Optional[int]] = so.mapped_column(sa.Integer())


class Like_Comment(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id, ondelete="CASCADE"), nullable=False)
    comment_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(Comment.id, ondelete="CASCADE"), nullable=False)
    timestamp: so.Mapped[datetime] = so.mapped_column(
        index=True, default=lambda: datetime.now(timezone.utc))