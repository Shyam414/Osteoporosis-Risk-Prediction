# routes/auth.py
import re
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
)
from itsdangerous import (
    BadSignature,
    SignatureExpired,
    URLSafeTimedSerializer,
)
from utils.security import check_password_hash, generate_password_hash
from run import limiter, mongo, mail, redis_client
from flask_mail import Message
from utils.validators import (
    login as login_required,
    refresh_login,
)


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

def get_serializer():
    return URLSafeTimedSerializer(current_app.secret_key)


# REGISTER
@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()

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

        msg = Message(
            subject="Verify Your MediLens Account",
            recipients=[email]
        )

        msg.html = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:40px;">
            <div style="
                max-width:600px;
                margin:auto;
                background:white;
                padding:30px;
                border-radius:8px;
                box-shadow:0 2px 8px rgba(0,0,0,.15);
                text-align:center;
            ">

                <h2 style="color:#2c3e50;">
                    Welcome to MediLens
                </h2>

                <p>
                    Thank you for registering.
                </p>

                <p>
                    Please verify your email address by clicking the button below.
                </p>

                <p style="margin:35px 0;">
                    <a href="{link}"
                        style="
                            background:#28a745;
                            color:white;
                            padding:14px 28px;
                            text-decoration:none;
                            border-radius:6px;
                            font-weight:bold;
                        ">
                        Verify Email
                    </a>
                </p>

                <p>
                    This verification link will expire in
                    <strong>1 hour</strong>.
                </p>

                <hr>

                <p style="font-size:13px;color:#777;">
                    If you didn't create this account,
                    simply ignore this email.
                </p>

            </div>
        </body>
        </html>
        """

        mail.send(msg)

    except Exception as e:
        current_app.logger.exception(f"Mail send failed: {e}")

    return jsonify({
        "msg": "Registered. Please check your email to verify."
    }), 201

# LOGIN
@auth_bp.route("/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()

    user = mongo.db.users.find_one(
        {"email": email},
        {"password": 1, "verified": 1, "role": 1}
    )

    if not user or not check_password_hash(user["password"], password):
        return jsonify({"msg": "Invalid email or password"}), 401

    if not user.get("verified", False):
        return jsonify({"msg": "Please verify email first"}), 403

    user_id = str(user["_id"])

    access_token = create_access_token(identity=user_id)
    refresh_token = create_refresh_token(identity=user_id)

    redis_client.set(
        f"session:{user_id}",
        access_token,
        ex=current_app.config["JWT_ACCESS_TOKEN_EXPIRES"]
    )

    return jsonify({
        "msg": "Login successful",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "role": user.get("role", "user")
    }), 200

# EMAIL CONFIRM
@auth_bp.route("/confirm/<token>")
def confirm_email(token):
    s = get_serializer()
    try:
        email = s.loads(
            token,
            salt="email-confirm",
            max_age=3600
        )

    except SignatureExpired:

        return (
            """
            <html>
            <body style="font-family:Arial;text-align:center;padding:80px;">
                <h2 style="color:#dc3545;">Verification Link Expired</h2>
                <p>Please register again or request a new verification email.</p>
            </body>
            </html>
            """,
            400,
            {"Content-Type": "text/html"}
        )

    except BadSignature:

        return (
            """
            <html>
            <body style="font-family:Arial;text-align:center;padding:80px;">
                <h2 style="color:#dc3545;">Invalid Verification Link</h2>
                <p>This verification link is not valid.</p>
            </body>
            </html>
            """,
            400,
            {"Content-Type": "text/html"}
        )

    user = mongo.db.users.find_one({"email": email})

    if not user:

        return (
            """
            <html>
            <body style="font-family:Arial;text-align:center;padding:80px;">
                <h2>User Not Found</h2>
            </body>
            </html>
            """,
            404,
            {"Content-Type": "text/html"}
        )

    if user.get("verified"):

        return (
            """
            <!DOCTYPE html>
            <html>
            <body style="font-family:Arial;background:#f5f5f5;">
                <div style="
                    max-width:500px;
                    margin:80px auto;
                    background:white;
                    padding:40px;
                    border-radius:10px;
                    text-align:center;
                    box-shadow:0 2px 10px rgba(0,0,0,.15);
                ">
                    <h2 style="color:#17a2b8;">
                        Email Already Verified
                    </h2>

                    <p>
                        Your account is already active.
                    </p>

                    <p>
                        You may now close this page.
                    </p>
                </div>
            </body>
            </html>
            """,
            200,
            {"Content-Type": "text/html"}
        )

    mongo.db.users.update_one(
        {"email": email},
        {"$set": {"verified": True}}
    )

    return (
        """
        <!DOCTYPE html>
        <html>
        <body style="font-family:Arial;background:#f5f5f5;">
            <div style="
                max-width:500px;
                margin:80px auto;
                background:white;
                padding:40px;
                border-radius:10px;
                text-align:center;
                box-shadow:0 2px 10px rgba(0,0,0,.15);
            ">
                <h2 style="color:#28a745;">
                    Email Verified Successfully
                </h2>

                <p>
                    Your account has been activated.
                </p>

                <p>
                    You can now close this page and log in to the application.
                </p>
            </div>
        </body>
        </html>
        """,
        200,
        {"Content-Type": "text/html"}
    )


# FORGOT PASSWORD
@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    if not email:
        return jsonify({"msg": "Email is required"}), 400

    user = mongo.db.users.find_one({"email": email})
    if not user:
        return jsonify({"msg": "Email not registered"}), 404

    try:
        s = get_serializer()
        token = s.dumps(email, salt="reset-password")
        link = f"{request.host_url}auth/reset-password/{token}"

        msg = Message(
            subject="Reset Your MediLens Password",
            recipients=[email]
        )

        msg.html = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family:Arial;background:#f5f5f5;padding:40px;">
        <div style="
        max-width:600px;
        margin:auto;
        background:white;
        padding:30px;
        border-radius:8px;
        text-align:center;
        box-shadow:0 2px 8px rgba(0,0,0,.15);
        ">

        <h2>Reset Your Password</h2>

        <p>We received a request to reset your password.</p>

        <p>
        <a href="{link}"
        style="
        background:#007bff;
        color:white;
        padding:14px 28px;
        text-decoration:none;
        border-radius:6px;
        font-weight:bold;
        ">
        Reset Password
        </a>
        </p>

        <p>This link expires in <b>30 minutes</b>.</p>

        <hr>

        <p style="color:#777;font-size:13px;">
        If you didn't request this, simply ignore this email.
        </p>

        </div>
        </body>
        </html>
        """
        mail.send(msg)

        return jsonify({"msg": "Password reset link sent"}), 200
    except Exception:
        current_app.logger.exception("Reset mail failed")
        return jsonify({"msg": "Could not send reset email"}), 500
    

@auth_bp.route("/reset-password/<token>", methods=["GET"])
def reset_password_page(token):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Reset Password</title>

        <style>
            body{{
                font-family:Arial,sans-serif;
                background:#f5f5f5;
                display:flex;
                justify-content:center;
                align-items:center;
                height:100vh;
                margin:0;
            }}

            .card{{
                background:white;
                width:420px;
                padding:40px;
                border-radius:10px;
                box-shadow:0 2px 10px rgba(0,0,0,.15);
                text-align:center;
            }}

            input{{
                width:100%;
                padding:12px;
                margin:18px 0;
                box-sizing:border-box;
            }}

            button{{
                width:100%;
                padding:12px;
                border:none;
                border-radius:5px;
                background:#28a745;
                color:white;
                cursor:pointer;
                font-size:16px;
            }}

            button:hover{{
                background:#218838;
            }}
        </style>
    </head>

    <body>

    <div class="card">

        <h2>Reset Password</h2>

        <input
            type="password"
            id="password"
            placeholder="Enter New Password"
        >

        <button onclick="resetPassword()">
            Reset Password
        </button>

    </div>

    <script>

    async function resetPassword() {{

        const password =
            document.getElementById("password").value;

        const res = await fetch("/auth/reset-password", {{
            method:"POST",
            headers:{{
                "Content-Type":"application/json"
            }},
            body:JSON.stringify({{
                token:"{token}",
                password:password
            }})
        }});

        const html = await res.text();

        document.open();
        document.write(html);
        document.close();

    }}

    </script>

    </body>
    </html>
    """

# RESET PASSWORD
@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():

    data = request.get_json() or {}

    token = data.get("token")

    new_pw = data.get("password","").strip()

    if not token or not new_pw:
        return """
        <h2>Token and password required.</h2>
        """,400

    s = get_serializer()

    try:

        email = s.loads(
            token,
            salt="reset-password",
            max_age=1800
        )

    except SignatureExpired:

        return """
        <!DOCTYPE html>
        <html>
        <body style="font-family:Arial;background:#f5f5f5;">
            <div style="
                max-width:500px;
                margin:80px auto;
                background:white;
                padding:40px;
                border-radius:10px;
                text-align:center;
                box-shadow:0 2px 10px rgba(0,0,0,.15);
            ">
                <h2 style="color:#dc3545;">
                    Reset Link Expired
                </h2>

                <p>Please request a new password reset email.</p>

            </div>
        </body>
        </html>
        """,400,{"Content-Type":"text/html"}

    except BadSignature:

        return """
        <!DOCTYPE html>
        <html>
        <body style="font-family:Arial;background:#f5f5f5;">
            <div style="
                max-width:500px;
                margin:80px auto;
                background:white;
                padding:40px;
                border-radius:10px;
                text-align:center;
                box-shadow:0 2px 10px rgba(0,0,0,.15);
            ">
                <h2 style="color:#dc3545;">
                    Invalid Reset Link
                </h2>

                <p>This reset link is invalid.</p>

            </div>
        </body>
        </html>
        """,400,{"Content-Type":"text/html"}

    if len(new_pw) < 8 or not re.search(
        r"[!@#$%^&*(),.?\":{{}}|<>]",
        new_pw
    ):

        return """
        <!DOCTYPE html>
        <html>
        <body style="font-family:Arial;background:#f5f5f5;">
            <div style="
                max-width:500px;
                margin:80px auto;
                background:white;
                padding:40px;
                border-radius:10px;
                text-align:center;
                box-shadow:0 2px 10px rgba(0,0,0,.15);
            ">
                <h2 style="color:#dc3545;">
                    Weak Password
                </h2>

                <p>
                    Password must be at least 8 characters
                    and contain one special character.
                </p>

            </div>
        </body>
        </html>
        """,400,{"Content-Type":"text/html"}

    hashed = generate_password_hash(new_pw)

    mongo.db.users.update_one(
        {"email":email},
        {
            "$set":{
                "password":hashed,
                "verified":True
            }
        }
    )

    return """
    <!DOCTYPE html>
    <html>
    <head>

        <title>Password Reset Successful</title>

        <style>

        body{
            font-family:Arial,sans-serif;
            background:#f5f5f5;
            display:flex;
            justify-content:center;
            align-items:center;
            height:100vh;
            margin:0;
        }

        .card{
            background:white;
            padding:40px;
            border-radius:10px;
            text-align:center;
            max-width:500px;
            box-shadow:0 2px 10px rgba(0,0,0,.15);
        }

        h2{
            color:#28a745;
        }

        </style>

    </head>

    <body>

        <div class="card">

            <h2>✅ Password Reset Successful</h2>

            <p>
                Your password has been updated successfully.
            </p>

            <p>
                You can now close this page and log in
                using your new password.
            </p>

        </div>

    </body>

    </html>
    """,200,{"Content-Type":"text/html"}

# REFRESH TOKEN
@auth_bp.route("/refresh", methods=["POST"])
@refresh_login
def refresh():
    user_id = get_jwt_identity()

    new_access = create_access_token(identity=user_id)

    redis_client.set(
        f"session:{user_id}",
        new_access,
        ex=current_app.config["JWT_ACCESS_TOKEN_EXPIRES"]
    )

    return jsonify({
        "access_token": new_access
    }), 200

# LOGOUT
@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    user_id = get_jwt_identity()
    redis_client.delete(f"session:{user_id}")
    return jsonify({"msg": "Logged out"}), 200
