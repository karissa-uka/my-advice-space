from flask_sqlalchemy import SQLAlchemy
from uuid import uuid4
from datetime import datetime

db = SQLAlchemy()

def get_uuid():
    return uuid4().hex

# Association table for the many-to-many relationship between users (friends)
friends_association = db.Table('friends_association',
    db.Column('user_id', db.String(32), db.ForeignKey('users.id')),
    db.Column('friend_id', db.String(32), db.ForeignKey('users.id'))
)

# Association table for the many-to-many relationship between users and posts (likes)
likes_association = db.Table('likes_association',
    db.Column('user_id', db.String(32), db.ForeignKey('users.id')),
    db.Column('post_id', db.String(32), db.ForeignKey('posts.id'))
)

dislikes_association = db.Table('dislikes_association',
    db.Column('user_id', db.String(32), db.ForeignKey('users.id')),
    db.Column('post_id', db.String(32), db.ForeignKey('posts.id'))
)


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.String(32), primary_key=True, unique=True, default=get_uuid)
    first_name = db.Column(db.String(300))
    last_name = db.Column(db.String(300))
    email = db.Column(db.String(345), unique=True)
    password = db.Column(db.Text, nullable=False)
    picture_path = db.Column(db.String(255))
    occupation = db.Column(db.String(100))
    location = db.Column(db.String(100))

    posts = db.relationship('Post', backref='user', lazy=True)
    comments = db.relationship('Comment', backref='user', lazy=True)
    # space_memberships = db.relationship('Space', secondary='space_memberships', back_populates='members')
    space_memberships = db.relationship('SpaceMembership', backref='user')
    
    # Define the many-to-many relationship on the User side
    friends = db.relationship('User', secondary=friends_association, 
                              primaryjoin=(friends_association.c.user_id == id),
                              secondaryjoin=(friends_association.c.friend_id == id),
                              backref=db.backref('friends_association', lazy='dynamic'))

    # Define the many-to-many relationship for liked posts
    liked_posts = db.relationship('Post', secondary=likes_association,
                                backref=db.backref('liked_by', lazy='dynamic'))
    
    disliked_posts = db.relationship('Post', secondary=dislikes_association,
                                     backref=db.backref('disliked_by', lazy='dynamic'))

class Post(db.Model):
    __tablename__ = 'posts'

    id = db.Column(db.String(32), primary_key=True, unique=True, default=get_uuid)
    user_id = db.Column(db.String(32), db.ForeignKey('users.id'), nullable=False)
    first_name = db.Column(db.String(300))
    last_name = db.Column(db.String(300))
    content = db.Column(db.Text, nullable=False)
    post_image = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Define the one-to-many relationship for comments
    #comments = db.relationship('Comment', backref='post', lazy=True)

    # Define the many-to-many relationship for likes
    likes = db.relationship('User', secondary=likes_association,
                            backref=db.backref('liked', lazy='dynamic'),
                            cascade='all, delete-orphan', single_parent=True)
    
    dislikes = db.relationship('User', secondary=dislikes_association,
                                backref=db.backref('disliked', lazy='dynamic'),
                                cascade='all, delete-orphan', single_parent=True)

    @property
    def like_count(self):
        return len(self.likes)
    
    @property
    def dislike_count(self):
        return len(self.dislikes)
    

class Comment(db.Model):
    __tablename__ = 'comments'

    id = db.Column(db.String(32), primary_key=True, unique=True, default=get_uuid)
    post_id = db.Column(db.String(32), db.ForeignKey('posts.id'), nullable=False)
    user_id = db.Column(db.String(32), db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    post = db.relationship('Post', backref='comments', lazy=True)

class Space(db.Model):
    __tablename__ = 'spaces'

    id = db.Column(db.String(32), primary_key=True, unique=True, default=get_uuid)
    title = db.Column(db.String(255), nullable=False)
    is_public = db.Column(db.Boolean, default=True)
    creator_id = db.Column(db.String(32), db.ForeignKey('users.id'), nullable=False)

    # Establish a relationship back to the user (creator of the space)
    creator = db.relationship('User', backref='created_spaces', lazy=True)

    # Define the many-to-many relationship with users through the 'memberships' table
    members = db.relationship('User', secondary='space_memberships', backref='spaces')

    def is_member(self, user_id):
        """
        Check if the user with the given user_id is a member of this space.
        """
        return user_id in [member.id for member in self.members]

    def add_member(self, user_id):
        """
        Add a user with the given user_id as a member of this space.
        """
        user = User.query.get(user_id)
        if user:
            self.members.append(user)
    
class SpaceMembership(db.Model):
    __tablename__ = 'space_memberships'

    user_id = db.Column(db.String(32), db.ForeignKey('users.id'), primary_key=True)
    space_id = db.Column(db.String(32), db.ForeignKey('spaces.id'), primary_key=True)

    # user = db.relationship('User', back_populates='spaces')
    # space = db.relationship('Space', back_populates='memberships')
    
class Discussion(db.Model):
    __tablename__ = 'discussions'

    id = db.Column(db.String(32), primary_key=True, unique=True, default=get_uuid)
    user_id = db.Column(db.String(32), db.ForeignKey('users.id'), nullable=False)
    space_id = db.Column(db.String(32), db.ForeignKey('spaces.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='discussions', lazy=True)
    space = db.relationship('Space', backref='discussions', lazy=True)
    
class DiscussionComment(db.Model):
    __tablename__ = 'discussion_comments'

    id = db.Column(db.String(32), primary_key=True, unique=True, default=get_uuid)
    user_id = db.Column(db.String(32), db.ForeignKey('users.id'), nullable=False)
    space_id = db.Column(db.String(32), db.ForeignKey('spaces.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    discussion_id=db.Column(db.String(32), db.ForeignKey('discussions.id'), nullable=False)

    # user = db.relationship('User', backref='discussions', lazy=True)
    # space = db.relationship('Space', backref='discussions', lazy=True)