# routes/auth.py
import re
from flask import Blueprint, request, jsonify, current_app, redirect
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from run import mongo, mail, limiter

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

def get_serializer():
    return URLSafeTimedSerializer(current_app.secret_key)

def frontend_url():
    return current_app.config["FRONTEND_URL"]

# REGISTER
@auth_bp.route("/register", methods=["POST"])
def register():
    email = request.json.get("email", "").strip().lower()
    password = request.json.get("password", "").strip()

    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({"msg": "Invalid email"}), 400

    if len(password) < 8 or not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return jsonify({"msg": "Weak password"}), 400

    if mongo.db.users.find_one({"email": email}):
        return jsonify({"msg": "Email already registered"}), 400

    hashed = generate_password_hash(password)

    mongo.db.users.insert_one({
        "email": email,
        "password": hashed,
        "verified": False,
        "role": "user"   
    })

    # send verification email
    try:
        s = get_serializer()
        token = s.dumps(email, salt="email-confirm")
        link = f"{request.host_url}auth/confirm/{token}"

        msg = Message("Confirm your account", recipients=[email])
        msg.body = f"Click to verify your account:\n{link}\n\nLink valid for 1 hour."
        mail.send(msg)
    except Exception:
        current_app.logger.exception("Mail send failed")

    return jsonify({"msg": "Registered. Please check your email to verify."}), 201


# EMAIL CONFIRM
@auth_bp.route("/confirm/<token>")
def confirm_email(token):
    s = get_serializer()
    try:
        email = s.loads(token, salt="email-confirm", max_age=3600)
    except SignatureExpired:
        return "Verification link expired", 400
    except BadSignature:
        return "Invalid verification link", 400

    mongo.db.users.update_one({"email": email}, {"$set": {"verified": True}})
    return redirect(f"{frontend_url()}/login.html")


# LOGIN
@auth_bp.route("/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():
    email = request.json.get("email", "").strip().lower()
    password = request.json.get("password", "").strip()

    user = mongo.db.users.find_one({"email": email},{"password": 1, "verified": 1, "role": 1})

    if not user or not check_password_hash(user["password"], password):
        return jsonify({"msg": "Invalid email or password"}), 401

    if not user.get("verified", False):
        return jsonify({"msg": "Please verify email first"}), 403

    user_id = str(user["_id"])
    access_token = create_access_token(identity=user_id)
    refresh_token = create_refresh_token(identity=user_id)

    return jsonify({
        "msg": "Login successful",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "role": user.get("role", "user")  
    }), 200


# FORGOT PASSWORD
@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    email = request.get_json().get("email", "").strip().lower()
    if not email:
        return jsonify({"msg": "Email is required"}), 400

    user = mongo.db.users.find_one({"email": email})
    if not user:
        return jsonify({"msg": "Email not registered"}), 404

    try:
        s = get_serializer()
        token = s.dumps(email, salt="reset-password")
        link = f"{frontend_url()}/reset_password.html?token={token}"

        msg = Message("Reset your password", recipients=[email])
        msg.body = f"Reset your password:\n{link}\n\nExpires in 30 minutes."
        mail.send(msg)

        return jsonify({"msg": "Password reset link sent"}), 200
    except Exception:
        current_app.logger.exception("Reset mail failed")
        return jsonify({"msg": "Could not send reset email"}), 500


# RESET PASSWORD
@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json()
    token = data.get("token")
    new_pw = data.get("password", "").strip()

    if not token or not new_pw:
        return jsonify({"msg": "Token and password required"}), 400

    s = get_serializer()
    try:
        email = s.loads(token, salt="reset-password", max_age=1800)
    except SignatureExpired:
        return jsonify({"msg": "Reset link expired"}), 400
    except BadSignature:
        return jsonify({"msg": "Invalid reset link"}), 400

    if len(new_pw) < 8 or not re.search(r"[!@#$%^&*(),.?\":{}|<>]", new_pw):
        return jsonify({"msg": "Weak password"}), 400

    hashed = generate_password_hash(new_pw)

    mongo.db.users.update_one(
        {"email": email},
        {"$set": {"password": hashed, "verified": True}}
    )

    return jsonify({"msg": "Password reset successful"}), 200


# REFRESH TOKEN
@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    user_id = get_jwt_identity()
    return jsonify({
        "access_token": create_access_token(identity=user_id)
    }), 200


# LOGOUT
@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    return jsonify({"msg": "Logged out"}), 200
