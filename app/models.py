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


        

class Post(db.Model):
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


    def __repr__(self):
        return '<Post {}>'.format(self.title)

