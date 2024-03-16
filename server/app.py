import re
from flask import Flask, request, jsonify, session, render_template, send_from_directory, redirect
from flask_bcrypt import Bcrypt
from flask_cors import CORS, cross_origin
from flask_session import Session
from flask_migrate import Migrate
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.exc import SQLAlchemyError
from flask_admin import Admin
from flask_admin .contrib.sqla import ModelView
import os
from config import ApplicationConfig
from models import db, User, Post, Comment, Space, Discussion, DiscussionComment
import traceback
from string import ascii_uppercase

app = Flask(__name__)
app.config.from_object(ApplicationConfig)
basedir = os.path.abspath(os.path.dirname(__file__))
admin = Admin()

bcrypt = Bcrypt(app)
CORS(app, supports_credentials=True, resources={r"/*/*": {"origins": "*"}})
server_session = Session(app)
db.init_app(app)
admin.init_app(app)
migrate = Migrate(app, db)

admin.add_view(ModelView(User, db.session))
admin.add_view(ModelView(Post, db.session))
admin.add_view(ModelView(Comment, db.session))
admin.add_view(ModelView(Space, db.session))
admin.add_view(ModelView(Discussion, db.session))
admin.add_view(ModelView(DiscussionComment, db.session))

with app.app_context():
    db.create_all()

@app.route("/@me", methods=['POST'])
def get_current_user():
    user_id = session.get("user_id")

    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    
    user = User.query.filter_by(id=user_id).first()
    return jsonify({
        "id": user.id,
        "email": user.email
    }) 

@app.route("/users/<email>", methods=["GET"])
def get_user_by_email(email):
    try:
        user = User.query.filter_by(email=email).first()

        if not user:
            return jsonify({"error": "User not found"}), 404

        return jsonify({
            "id": user.id,
            "email": user.email,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "occupation": user.occupation,
            "user_picture": user.picture_path,
        })

    except Exception as e:
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
    
@app.route('/assets/<path:filename>')
def serve_static(filename):
    return send_from_directory('assets', filename)

@app.route("/register", methods=["POST"])
def register_user():
    try:
        data = request.get_json()
        first_name = data.get("firstName")
        last_name = data.get("lastName")
        email = data.get("email")
        password = data.get("password")
        hashed_password = bcrypt.generate_password_hash(password)
        confirm_password = data.get("confirmPassword")
        user_picture = data.get("picture")
        occupation = data.get("occupation")

        response_data = {}

        if not first_name or not last_name:
            response_data['error'] = "First name and last name are required"
            return jsonify(response_data), 400

        if not email or not re.match(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b', email):
            response_data['error'] = "Please insert a valid email"
            return jsonify(response_data), 400

        if not password:
            response_data['error'] = "Please enter your password"
            return jsonify(response_data), 400

        if len(password) <= 8 or not re.search(r'\d', password) or not re.search(r'[A-Z]', password) \
                or not re.search(r'[a-z]', password) or not re.search(r'[\'^£$%&*()}{@#~?!><>,|=_+¬-]', password):
            response_data['error'] = "Invalid password format"
            return jsonify(response_data), 400
        
        if not occupation:
            response_data['error'] = "Please state your occupation"
            return jsonify(response_data), 400

        if confirm_password != password:
            response_data['error'] = "Passwords do not match"
            return jsonify(response_data), 400

        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            response_data['error'] = 'User already exists'
            return jsonify(response_data), 409
        
        if user_picture:
            print(user_picture)
            # Process and save the picture as needed
            user_picture_path = os.path.join(basedir, "assets", user_picture.filename)
            user_picture.save(user_picture_path)
            
            new_user = User(first_name=first_name, last_name=last_name, email=email, password=hashed_password, picture_path=user_picture.filename, occupation=occupation)
            
        else: 
            new_user = User(first_name=first_name, last_name=last_name, email=email, password=hashed_password, occupation=occupation)
        
        print(response_data)
        db.session.add(new_user)
        db.session.commit()

        session["user_id"] = new_user.id

        friends_list = [{
                "id": friend.id,
                "firstName": friend.first_name,
                "lastName": friend.last_name,
                "email": friend.email,
            } for friend in new_user.friends]

        return jsonify({
            "id": new_user.id,
            "email": new_user.email,
            "firstName": new_user.first_name,
            "lastName": new_user.last_name,
            "friends": friends_list,
            "occupation": new_user.occupation,
            "user_picture": new_user.picture_path,
        }), 201
    
    except Exception as e:
        print(e)
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500

@app.route("/login", methods=["POST"])
def login_user():
    try:
        data = request.get_json()
        email = data.get("email")
        password = data.get("password")

        user = User.query.filter_by(email=email).first()

        if user is None or not bcrypt.check_password_hash(user.password, password):
            return jsonify({"error": "Unauthorized"}), 401

        session["user_id"] = user.id

        print("Session:", session) 

        friends_list = [{
                "id": friend.id,
                "firstName": friend.first_name,
                "lastName": friend.last_name,
                "email": friend.email,
            } for friend in user.friends]

        return jsonify({
            "id": user.id,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "email": user.email,
            "friends": friends_list,
            "occupation": user.occupation,
            "user_picture": user.picture_path,
        })
    except Exception as e:
        print(e)
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500

@app.route("/logout", methods=["POST"])
def logout_user():
    session.pop("user_id", None)
    return jsonify({"message": "Successfully logged out"}), 200

@app.route("/additional-details", methods=["POST"])
def additional_details():
    user_picture = request.files.get("picture")
    user_id = session.get("user_id")
    user = User.query.filter_by(id=user_id).first()
    
    if not user:
        return jsonify({"error": "User not found"}), 400
    
    if user_picture:
            print(user_picture)
            # Process and save the picture as needed
            user_picture_path = os.path.join(basedir, "assets", user_picture.filename)
            user_picture.save(user_picture_path)
            user.picture_path = user_picture.filename
            
            db.session.commit()
    
    friends_list = [{
                "id": friend.id,
                "firstName": friend.first_name,
                "lastName": friend.last_name,
                "email": friend.email,
            } for friend in user.friends]
                
    return jsonify({
            "id": user.id,
            "email": user.email,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "user_picture": user.picture_path,
            "friends": friends_list,
            "occupation": user.occupation,
        })       
   
users_settings = {}

@app.route('/update-settings', methods=['POST'])
def update_settings():
    data = request.json

    # Extracting data from the request
    user_id = data.get('user_id')  
    first_name = data.get('firstName')
    last_name = data.get('lastName')
    email = data.get('email')
    password = data.get('password')
    notification_preferences = data.get('notificationPreferences')

    # Update user settings in backend logic
    # to perform validation, authentication, and then update the settings accordingly
    users_settings[user_id] = {
        'firstName': first_name,
        'lastName': last_name,
        'email': email,
        'password': password,
        'notification_preferences': notification_preferences
    }

    return jsonify({'message': 'User settings updated successfully'})

@app.route("/posts", methods=["POST"])
def create_post():
    try:
        user_id = session.get("user_id")
        print("Session:", session)
        data = request.form
        if user_id is None:
            print("No user session found")
            return jsonify({"error": "Unauthorized"}), 401

        user = User.query.filter_by(id=user_id).first()

        if not user:
            return jsonify({"error": "User not found"}), 404
        

        content = request.form.get("description")
        created_at = request.form.get("created_at")
        picture = request.files.get("picture")
        last_name = request.form.get("lastName")
        first_name = request.form.get("firstName")

        print("Content:", content)

        if not content:
            print("no content found")
            return jsonify({"error": "Content is required"}), 400

        if picture:
            print(picture)
            # Process and save the picture as needed
            picture_path = os.path.join(basedir, "assets", picture.filename)
            picture.save(picture_path)
            new_post = Post(user_id=user.id, content=content, created_at=created_at, post_image=picture.filename, last_name=last_name, first_name=first_name)

        else:
            new_post = Post(user_id=user.id, content=content, created_at=created_at, last_name=last_name, first_name=first_name)


        db.session.add(new_post)
        db.session.commit()
        posts = Post.query.all()
       

        post_list = [{
            "id": post.id,
            "user_id": post.user_id,
            "content": post.content,
            "created_at": post.created_at,
            "picture": post.post_image,
            "lastName": post.last_name,
            "firstName": post.first_name,
            "userPicturePath": post.user.picture_path,
            "likes": post.like_count,
            "dislikes": post.dislike_count,
            "comments": [{
                "content": comment.content,
                "user_id": comment.user_id,
                "post_id": comment.post_id,
                "firstName": comment.user.first_name,
                "lastName": comment.user.last_name,
                "userPicturePath": comment.user.picture_path,
            } for comment in Comment.query.filter_by(post_id=post.id).all()]
        } for post in posts]

        return jsonify(post_list)
    
    except Exception as e:
        print(e)
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500

@app.route("/posts", methods=["GET"])
def get_all_posts():
    try:
        posts = Post.query.all()

        post_list = [{
            "id": post.id,
            "user_id": post.user_id,
            "content": post.content,
            "created_at": post.created_at,
            "picture": post.post_image,
            "lastName": post.last_name,
            "firstName": post.first_name,
            "userPicturePath": post.user.picture_path,
            "likes": post.like_count,
            "dislikes": post.dislike_count,
            "comments": [{
                "content": comment.content,
                "user_id": comment.user_id,
                "post_id": comment.post_id,
                "firstName": comment.user.first_name,
                "lastName": comment.user.last_name,
                "userPicturePath": comment.user.picture_path,
            } for comment in post.comments]
        } for post in posts]

        return jsonify(post_list)
    except Exception as e:
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
    
@app.route("/delete/<id>", methods=["POST", "OPTIONS"])
@cross_origin(supports_credentials=True)
def delete_post(id):
    if request.method == "OPTIONS":
        return jsonify(), 200

    post = Post.query.get(id)
    user_id = session.get('user_id')
    logged_user = User.query.filter_by(id=user_id).first()
    
    if not logged_user:
            return jsonify({"error": "User not found"}), 404

    if not post:
        return jsonify({"Error": "Post not found"}), 404

    try:
        for user in post.liked_by:
            post.liked_by.remove(user)
            db.session.commit()
        for user in post.disliked_by:
            post.disliked_by.remove(user)
            db.session.commit()      
        comments = Comment.query.filter_by(post_id=post.id).all()
        for comment in comments:
            db.session.delete(comment)
            db.session.commit()
            
        db.session.delete(post)
        db.session.commit()
    except StaleDataError as e:
        db.session.rollback()
        print(e)
        return jsonify({"Error": "Stale Data Error - Row may have been deleted by another process"}), 500
    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"Error": f"Internal Server Error: {str(e)}"}), 500

    posts = Post.query.all()

    post_list = [{
        "id": post.id,
        "user_id": post.user_id,
        "content": post.content,
        "created_at": post.created_at,
        "picture": post.post_image,
        "lastName": post.last_name,
        "firstName": post.first_name,
        "userPicturePath": post.user.picture_path,
        "likes": post.like_count,
        "dislikes": post.dislike_count,
        "comments": [{
            "content": comment.content,
            "user_id": comment.user_id,
            "post_id": comment.post_id,
            "firstName": comment.user.first_name,
            "lastName": comment.user.last_name,
            "userPicturePath": comment.user.picture_path,
        } for comment in Comment.query.filter_by(post_id=post.id).all()]
    } for post in posts]
    
    return jsonify(post_list), 200

@app.route("/users/<user_id>/friends", methods=["GET"])
def get_friends(user_id):
    user = User.query.get(user_id)

    if not user:
            return jsonify({"error": "User or friend not found"}), 404
    
    friends = user.friends

    friends_list = [{
            "id": friend.id,
            "firstName": friend.first_name,
            "lastName": friend.last_name,
            "email": friend.email,
            "occupation": friend.occupation,
            "picturePath": friend.picture_path,
        } for friend in friends]
    
    response = jsonify(friends_list)

    return response

@app.route("/users/<user_id>/<friend_id>", methods=["PATCH", "DELETE"])
@cross_origin(supports_credentials=True)
def update_friend_list(user_id, friend_id):
    if request.method == "DELETE":
        try:
            user = db.session.query(User).filter_by(id=user_id).first()
            friend = db.session.query(User).filter_by(id=friend_id).first()

            if not user or not friend:
                return jsonify({"error": "User or friend not found"}), 404
            
            user.friends.remove(friend)
            db.session.commit()

            friends = user.friends

            friends_list = [{
                    "id": friend.id,
                    "firstName": friend.first_name,
                    "lastName": friend.last_name,
                    "email": friend.email,
                    "occupation": friend.occupation,
                    "picturePath": friend.picture_path,
                } for friend in friends]

            response = jsonify(friends_list)
            return response

        except Exception as e:
            print(f"Error during friend deletion: {e}")
            traceback.print_exc()  
            db.session.rollback() 
            return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
        
    else:
        try:
            user = User.query.filter_by(id=user_id).first()
            friend = User.query.filter_by(id=friend_id).first()
            print(str(friend))

            print(f"Friend ID: {friend_id}")

            if not user or not friend:
                return jsonify({"error": "User or friend not found"}), 404
            
            db.session.add(user)

            if friend not in user.friends:
                print("Adding new friend..")
                user.friends.append(friend)
                db.session.commit()
                print(f"Commit successful for user {user.id}")

            friends = user.friends
            print(str(friends))

            friends_list = [{
                "id": friend.id,
                "firstName": friend.first_name,
                "lastName": friend.last_name,
                "email": friend.email,
                "occupation": friend.occupation,
                "picturePath": friend.picture_path,
            } for friend in friends]

            response = jsonify(friends_list)

            return response
        except Exception as e:
            traceback.print_exc()  # Print the traceback
            db.session.rollback()  # Rollback to avoid leaving the database in an inconsistent state
            print(f"Error during friend addition: {e}")
            return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500     
        
@app.route("/posts/<post_id>/like", methods=["PATCH"])
def like_post(post_id):
    try:
        user_id = session.get("user_id")
        print("User ID:", user_id)

        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401

        user = User.query.filter_by(id=user_id).first()

        if not user:
            return jsonify({"error": "User not found"}), 404

        post = Post.query.filter_by(id=post_id).first()

        if not post:
            return jsonify({"error": "Post not found"}), 404

        if post in user.liked:
            return jsonify({"error": "User already liked the post"}), 400
        if user in post.disliked_by:
            post.disliked_by.remove(user)

        user.liked.append(post)
        db.session.commit()
        
        post_data = {
            "id": post.id,
            "user_id": post.user_id,
            "content": post.content,
            "created_at": post.created_at,
            "picture": post.post_image,
            "lastName": post.last_name,
            "firstName": post.first_name,
            "userPicturePath": post.user.picture_path,
            "likes": post.like_count,
            "dislikes": post.dislike_count,
        }
        
        
        return jsonify({"message": "Post liked successfully", "post": post_data }), 200

    except Exception as e:
        print(e)
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
    
@app.route("/posts/<post_id>/dislike", methods=["PATCH"])
def dislike_post(post_id):
    try:
        user_id = session.get("user_id")

        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401

        user = User.query.filter_by(id=user_id).first()

        if not user:
            return jsonify({"error": "User not found"}), 404

        post = Post.query.filter_by(id=post_id).first()

        if not post:
            return jsonify({"error": "Post not found"}), 404
        if user in post.liked_by:
            post.liked_by.remove(user)

        post.disliked_by.append(user)
        db.session.commit()
        return jsonify({"message": "Post dislike successful"}), 200

    except Exception as e:
        print(e)
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
    
@app.route("/posts/<post_id>/comment", methods=["POST"])
def post_comment(post_id):
    try:
        user_id = session.get("user_id")

        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401

        user = User.query.filter_by(id=user_id).first()

        if not user:
            return jsonify({"error": "User not found"}), 404

        post = Post.query.filter_by(id=post_id).first()

        if not post:
            return jsonify({"error": "Post not found"}), 404

        content = request.form.get("content")  

        if not content:
            return jsonify({"error": "Content is required"}), 400

        comment = Comment(user_id=user.id, post_id=post.id, content=content)
        post.comments.append(comment)
        db.session.commit()

        return jsonify({"message": "Comment posted successfully"}), 200

    except Exception as e:
        print(e)
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500

@app.route("/spaces", methods=["POST"])
def create_space():
    try:
        data = request.get_json()
        title = data.get("title")
        is_public = data.get("isPublic", True)

        # Validate the data as needed

        new_space = Space(title=title, is_public=is_public)
        db.session.add(new_space)
        db.session.commit()

        return jsonify({"space_id": new_space.id, "title": new_space.title}), 201

    except Exception as e:
        print(e)
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
    
@app.route("/spaces/<space_id>", methods=["GET"])
def get_space(space_id):
    try:
        space = Space.query.filter_by(id=space_id).first()
        space_data = {"id": space.id, "title": space.title, "isPublic": space.is_public}
        
        return jsonify(space_data), 201
    
    except Exception as e:
        print(e)
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
    
@app.route("/spaces", methods=["GET"])
def get_spaces():
    try:
        spaces = Space.query.all()
        space_list = [{"id": space.id, "title": space.title, "isPublic": space.is_public} for space in spaces]

        return jsonify({"spaces": space_list})

    except Exception as e:
        print(e)
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
    
@app.route("/users/<user_id>/spaces", methods=["GET"])
def get_user_spaces(user_id):
    try:
        user = User.query.get(user_id)

        if not user:
            return jsonify({"error": "User not found"}), 404

        user_spaces = user.joined_spaces

        space_list = [{"id": space.id, "title": space.title} for space in user_spaces]

        return jsonify({"spaces": space_list})

    except Exception as e:
        print(e)
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500

@app.route("/spaces/<space_id>", methods=["DELETE"])
def delete_space(space_id):
    try:
        user_id = session.get("user_id")

        if not user_id:
            print("Unauthorized: User not authenticated")
            return jsonify({"error": "Unauthorized"}), 401

        user = User.query.filter_by(id=user_id).first()

        if not user:
            print("User not found")
            return jsonify({"error": "User not found"}), 404

        space = Space.query.filter_by(id=space_id).first()

        if not space:
            print("Space not found")
            return jsonify({"error": "Space not found"}), 404

        print(f"User ID: {user.id}, Space Creator ID: {space.creator_id}")

        if user.id != space.creator_id:
            print("Permission denied. User is not the creator of this space")
            return jsonify({"error": "Permission denied. You are not the creator of this space"}), 403

        db.session.delete(space)
        db.session.commit()
        print(session)

        print("Space deleted successfully")

        return jsonify({"success": True, "message": "Space deleted successfully"}), 200

    except Exception as e:
        print(f"Error: {e}")
        db.session.rollback()
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
    
# Create and Get Discussions for a Space
@app.route("/spaces/<space_id>/discussions", methods=["POST", "GET"])
def handle_space_discussions(space_id):
    try:
        if request.method == "POST":
            # Create Discussion
            user_id = session.get("user_id")
            if not user_id:
                return jsonify({"error": "Unauthorized"}), 401

            space = Space.query.filter_by(id=space_id).first()
            if not space:
                return jsonify({"error": "Space not found"}), 404

            data = request.get_json()
            title = data.get("title")
            thoughts = data.get("thoughts")

            if not title or not thoughts:
                return jsonify({"error": "Title and thoughts are required"}), 400

            new_discussion = Discussion(user_id=user_id, space_id=space.id, title=title, content=thoughts)
            db.session.add(new_discussion)
            db.session.commit()

            return jsonify({
                "discussion_id": new_discussion.id,
                "user_id": user_id,
                "space_id": space.id,
                "title": new_discussion.title,
                "content": new_discussion.content,
                "created_at": new_discussion.created_at,
            }), 201

        elif request.method == "GET":
            # Get Discussions
            space = Space.query.filter_by(id=space_id).first()
            if not space:
                return jsonify({"error": "Space not found"}), 404

            discussions = Discussion.query.filter_by(space_id=space.id).all()
            discussions_data = [{
                "discussion_id": discussion.id,
                "user_id": discussion.user_id,
                "space_id": discussion.space_id,
                "title": discussion.title,
                "content": discussion.content,
                "created_at": discussion.created_at,
            } for discussion in discussions]

            return jsonify(discussions_data)

    except SQLAlchemyError as e:
        print(e)
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500

# Get, Update, and Delete Discussion Details
@app.route("/discussions/<discussion_id>", methods=["GET", "PUT", "DELETE"])
def handle_discussion_details(discussion_id):
    try:
        discussion = Discussion.query.filter_by(id=discussion_id).first()

        if not discussion:
            return jsonify({"error": "Discussion not found"}), 404

        if request.method == "GET":
            # Get Discussion Details
            discussion_data = {
                "discussion_id": discussion.id,
                "user_id": discussion.user_id,
                "space_id": discussion.space_id,
                "title": discussion.title,
                "content": discussion.content,
                "created_at": discussion.created_at,
            }
            return jsonify(discussion_data)

        elif request.method == "PUT":
            # Update Discussion
            data = request.get_json()
            discussion.title = data.get("title", discussion.title)
            discussion.content = data.get("content", discussion.content)
            db.session.commit()
            return jsonify({"message": "Discussion updated successfully"})

        elif request.method == "DELETE":
            # Delete Discussion
            db.session.delete(discussion)
            db.session.commit()
            return jsonify({"message": "Discussion deleted successfully"})

    except SQLAlchemyError as e:
        print(e)
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500

# Get Comments for a Discussion and Add Comment to a Discussion
@app.route("/discussions/<discussion_id>/comments", methods=["GET", "POST"])
def handle_discussion_comments(discussion_id):
    try:
        discussion = Discussion.query.filter_by(id=discussion_id).first()

        if not discussion:
            return jsonify({"error": "Discussion not found"}), 404

        if request.method == "GET":
            # Get Comments for a Discussion
            comments = DiscussionComment.query.filter_by(discussion_id=discussion.id).all()
            comments_data = [{
                "comment_id": comment.id,
                "user_id": comment.user_id,
                "space_id": comment.space_id,
                "discussion_id": comment.discussion_id,
                "content": comment.content,
                "created_at": comment.created_at,
            } for comment in comments]

            return jsonify({"comments": comments_data})

        elif request.method == "POST":
            # Add Comment to a Discussion
            user_id = session.get("user_id")
            user = User.query.filter_by(id=user_id).first()
            if not user:
                return jsonify({"error": "Unauthorized"}), 401

            data = request.get_json()
            content = data.get("content")

            if not content:
                return jsonify({"error": "Comment content is required"}), 400

            new_comment = DiscussionComment(user_id=user_id, title=discussion.title, discussion_id=discussion.id, space_id=discussion.space_id, content=content)
            db.session.add(new_comment)
            db.session.commit()

            return jsonify({
                "comment_id": new_comment.id,
                "user_id": new_comment.user_id,
                "space_id": new_comment.space_id,
                "discussion_id": new_comment.discussion_id,
                "content": new_comment.content,
                "created_at": new_comment.created_at,
            }), 201

    except SQLAlchemyError as e:
        print(e)
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
    
@app.route('/notifications/<string:user_id>', methods=['GET'])
def get_notifications(user_id):
    notification_type = request.args.get('type')
    user = User.query.get(user_id)

    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    notifications = []

    if notification_type == "friends" or notification_type is None:
        # Assuming "friends" involves retrieving users connected via an association table
        friend_ids = [f.id for f in user.friends]
        friends = User.query.filter(User.id.in_(friend_ids)).all()
        for friend in friends:
            notifications.append({
                'type': 'friend',
                'id': friend.id,
                'first_name': friend.first_name,
                'last_name': friend.last_name,
            })

    if notification_type == "comments" or notification_type is None:
        posts = Post.query.filter_by(user_id=user_id).all()
        post_ids = [post.id for post in posts]
        comments = Comment.query.filter(Comment.post_id.in_(post_ids)).all()
        for comment in comments:
            notifications.append({
                'type': 'comment',
                'post_id': comment.post_id,
                'content': comment.content,
                'created_at': comment.created_at,
                
            })

    if notification_type == "likes" or notification_type is None:
        posts = Post.query.filter_by(user_id=user_id).all()
        for post in posts:
            for like_user in post.likes:
                notifications.append({
                    'type': 'like',
                    'post_id': post.id,
                    'user_id': like_user.id,
                    'first_name': like_user.first_name,
                    'last_name': like_user.last_name,
                })

    if notification_type == "spaces" or notification_type is None:
        spaces = Space.query.filter_by(creator_id=user_id).all()
        for space in spaces:
            notifications.append({
                'type': 'space',
                'id': space.id,
                'title': space.title,
                'is_public': space.is_public,
                'created_at': space.created_at,  
            })

    if notification_type == "occupation" or notification_type is None:
        # Assuming the original route's intent was to notify users of others with the same occupation
        matches = User.query.filter(User.occupation == user.occupation, User.id != user_id).all()
        for match in matches:
            notifications.append({
                'type': 'occupation',
                'user_id': match.id,
                'first_name': match.first_name,
                'last_name': match.last_name,
                'occupation': match.occupation,
            })

    return jsonify(notifications)

if __name__ == "__main__":
    app.run(debug=True)