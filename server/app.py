import re
from flask import Flask, request, jsonify, session, render_template, send_from_directory, redirect
from flask_bcrypt import Bcrypt
from flask_cors import CORS, cross_origin
from flask_session import Session
from flask_migrate import Migrate
from flask_socketio import join_room, leave_room, send, emit, SocketIO
import os
from config import ApplicationConfig
from models import db, User, Post, Comment, Space
import traceback
import random
from string import ascii_uppercase

app = Flask(__name__)
app.config.from_object(ApplicationConfig)
basedir = os.path.abspath(os.path.dirname(__file__))

bcrypt = Bcrypt(app)
CORS(app, supports_credentials=True, resources={r"/*/*": {"origins": "*"}})
server_session = Session(app)
db.init_app(app)
migrate = Migrate(app, db)
socketio = SocketIO(app, cors_allowed_origins="*")  # Initialize SocketIO

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
        confirm_password = data.get("confirmPassword")

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

        if confirm_password != password:
            response_data['error'] = "Passwords do not match"
            return jsonify(response_data), 400

        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            response_data['error'] = 'User already exists'
            return jsonify(response_data), 409
        
        print(response_data)

        hashed_password = bcrypt.generate_password_hash(password)
        new_user = User(first_name=first_name, last_name=last_name, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        session["user_id"] = new_user.id

        return jsonify({
            "id": new_user.id,
            "email": new_user.email,
            "firstName": new_user.first_name,
            "lastName": new_user.last_name,
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
        })
    except Exception as e:
        print(e)
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500

@app.route("/logout", methods=["POST"])
def logout_user():
    session.pop("user_id", None)
    return jsonify({"message": "Successfully logged out"}), 200

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
        picture = request.files.get("picturePath")
        last_name = request.form.get("lastName")
        first_name = request.form.get("firstName")

        print("Content:", content)

        if not content:
            print("no content found")
            return jsonify({"error": "Content is required"}), 400

        if picture:
            # Process and save the picture as needed
            picture_path = os.path.join(basedir, "assets", picture.filename)
            picture.save(picture_path)

        new_post = Post(user_id=user.id, content=content, created_at=created_at, last_name=last_name, first_name=first_name)
        db.session.add(new_post)
        db.session.commit()
        posts = Post.query.all()

        post_list = [{
            "id": post.id,
            "user_id": post.user_id,
            "content": post.content,
            "created_at": post.created_at,
            "lastName": post.last_name,
            "firstName": post.first_name,
        } for post in posts]

        return jsonify(post_list)
    
    except Exception as e:
        print(e)
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500

# Add a new route to get all posts
@app.route("/posts", methods=["GET"])
def get_all_posts():
    try:
        posts = Post.query.all()

        post_list = [{
            "id": post.id,
            "user_id": post.user_id,
            "content": post.content,
            "created_at": post.created_at,
            "lastName": post.last_name,
            "firstName": post.first_name,
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

    if not post:
        return jsonify({"Error": "Post not found"}), 404

    db.session.delete(post)
    db.session.commit()
    posts = Post.query.all()

    post_list = [{
            "id": post.id,
            "user_id": post.user_id,
            "content": post.content,
            "created_at": post.created_at,
            "lastName": post.last_name,
            "firstName": post.first_name,
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
                } for friend in friends]

            response = jsonify(friends_list)
            return response

        except Exception as e:
            print(f"Error during friend deletion: {e}")
            traceback.print_exc()  # Print the traceback
            db.session.rollback()  # Rollback to avoid leaving the database in an inconsistent state
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

        if user in post.liked_by:
            return jsonify({"error": "User already liked the post"}), 400

        post.liked_by.append(user)
        db.session.commit()

        return jsonify({"message": "Post liked successfully"}), 200

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

        post.liked_by.remove(user)
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
        db.session.add(comment)
        db.session.commit()
        

        return jsonify({"message": "Comment posted successfully"}), 200

    except Exception as e:
        print(e)
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
    
@app.route("/send-message", methods=["POST"])
def send_message():
    try:
        data = request.get_json()
        text = data.get("text")
        uid = data.get("uid")
        photoURL = data.get("photoURL")

        # Create a new Comment, assuming you have a Comment model
        new_comment = Comment(user_id=uid, content=text)

        db.session.add(new_comment)
        db.session.commit()

        # You can emit the new message to all connected clients using SocketIO
        socketio.emit('new_message', {
            'text': text,
            'uid': uid,
            'photoURL': photoURL,
        }, broadcast=True)

        return jsonify({"message": "Message sent successfully"}), 200

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

        # Assuming you have a relationship in your User model that links to joined spaces
        user_spaces = user.joined_spaces

        space_list = [{"id": space.id, "title": space.title} for space in user_spaces]

        return jsonify({"spaces": space_list})

    except Exception as e:
        print(e)
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500


if __name__ == "__main__":
    socketio.run(app, debug=True)