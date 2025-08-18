from hashlib import md5
from typing import List
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db, login
from flask import current_app
from flask_login import UserMixin
from time import time
import jwt

followers = sa.Table(
    'followers',
    db.metadata,
    sa.Column('follower_id', sa.Integer, sa.ForeignKey('user.id', ondelete="CASCADE"), primary_key=True),
    sa.Column('followed_id', sa.Integer, sa.ForeignKey('user.id', ondelete="CASCADE"), primary_key=True)
)

class User(UserMixin, db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True, unique=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True, unique=True)
    password_hash: so.Mapped[str | None] = so.mapped_column(sa.String(256))
    role: so.Mapped[str] = so.mapped_column(
    sa.String(20), default="user", nullable=False
    )
    posts: so.WriteOnlyMapped['Post'] = so.relationship(back_populates='author', cascade='all, delete-orphan')
    about_me: so.Mapped[str | None] = so.mapped_column(sa.String(140))
    last_seen: so.Mapped[datetime | None] = so.mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    following: so.WriteOnlyMapped['User'] = so.relationship(
        secondary=followers, primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        back_populates='followers'
    )
    followers: so.WriteOnlyMapped['User'] = so.relationship(
        secondary=followers, primaryjoin=(followers.c.followed_id == id),
        secondaryjoin=(followers.c.follower_id == id),
        back_populates='following'
    )
    comments: so.WriteOnlyMapped['Comment'] = so.relationship(back_populates='author', cascade='all, delete-orphan')

    def __repr__(self) -> str:
        return f'<User {self.username}>'
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
            {'reset_password': self.id, 'exp': time() + expires_in},
            current_app.config['SECRET_KEY'], algorithm='HS256'
        )
    
    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])['reset_password']
        except:
            return
        return db.session.get(User, id)
    
    def avatar(self, size):
        digest = md5(self.email.lower().encode('utf-8')).hexdigest()
        return f'https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}'
    
    def follow(self, user):
        if not self.is_following(user):
            self.following.add(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.following.remove(user)

    def is_following(self, user):
        query = self.following.select().where(User.id == user.id)
        return db.session.scalar(query) is not None
    
    def followers_count(self):
        query = sa.select(sa.func.count()).select_from(
            self.followers.select().subquery()
        )
        return db.session.scalar(query)
    
    def following_count(self):
        query = sa.select(sa.func.count()).select_from(
            self.following.select().subquery()
        )
        return db.session.scalar(query)
    
    def following_posts(self):
        Author = so.aliased(User)
        Follower = so.aliased(User)
        return (
            sa.select(Post)
            .join(Post.author.of_type(Author))
            .join(Author.followers.of_type(Follower), isouter=True)
            .where(sa.or_(
                Follower.id == self.id,
                Author.id == self.id,
            ), Post.is_approved.is_(True))
            .distinct(Post.id)
            .order_by(Post.timestamp.desc())
        )
    
    def is_admin(self) -> bool:
        return self.role == "admin"

    def is_analyst(self) -> bool:
        return self.role == "analyst"
    
    def is_user(self) -> bool:
        return self.role == 'user'

    
class Post(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    title: so.Mapped[str] = so.mapped_column(sa.String(200))
    body: so.Mapped[str] = so.mapped_column(sa.String(500))
    image: so.Mapped[str | None] = so.mapped_column(sa.String(255), nullable=True)
    timestamp: so.Mapped[datetime] = so.mapped_column(
        index=True,
        default=lambda: datetime.now(timezone.utc)
    )
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id, ondelete="CASCADE"), index=True)
    author: so.Mapped[User] = so.relationship(back_populates='posts')
    comments: so.Mapped[List['Comment']] = so.relationship(back_populates='post', cascade='all, delete-orphan')
    is_approved: so.Mapped[bool] = so.mapped_column(default=False)

    def __repr__(self) -> str:
        return f'<Post {self.body}>'
    
    def get_comments(self, ascending: bool = True):
        order = Comment.timestamp.asc() if ascending else Comment.timestamp.desc()
        return sa.select(Comment).where(Comment.post_id == self.id).order_by(order)
    
    def comment_count(self):
        query = sa.select(sa.func.count()).where(Comment.post_id == self.id)
        return db.session.scalar(query)
    
@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))

class Comment(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    body: so.Mapped[str] = so.mapped_column(sa.String(200))
    timestamp: so.Mapped[datetime] = so.mapped_column(
        index=True,
        default=lambda: datetime.now(timezone.utc)
    )
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id, ondelete="CASCADE"), index=True)
    post_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(Post.id, ondelete="CASCADE"), index=True)
    author: so.Mapped[User] = so.relationship(back_populates='comments')
    post: so.Mapped[Post] = so.relationship(back_populates='comments')