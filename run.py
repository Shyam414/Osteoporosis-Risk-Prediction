import os
from dotenv import load_dotenv
from flask import Flask
from flask_pymongo import PyMongo
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_jwt_extended import JWTManager
from flask_redis import FlaskRedis
from flask_cors import CORS  

load_dotenv()

mongo = PyMongo()
mail = Mail()
limiter = Limiter(key_func=get_remote_address,storage_uri=os.getenv("REDIS_URL"))
jwt = JWTManager()
redis_client = FlaskRedis()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY", "supersecret")

    app.config["PROPAGATE_EXCEPTIONS"] = True

    # Environment configs
    app.config["MONGO_URI"] = os.getenv("MONGO_URI")
    app.config["ADMIN_EMAIL"] = os.getenv("ADMIN_EMAIL")
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "supersecretjwt")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = 900    #15    
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = 604800   #7days 
    app.config["UPLOAD_FOLDER"] = "uploads"

    app.config["REDIS_URL"] = os.getenv("REDIS_URL")
    app.config["AWS_ACCESS_KEY_ID"] = os.getenv("AWS_ACCESS_KEY_ID")
    app.config["AWS_SECRET_ACCESS_KEY"] = os.getenv("AWS_SECRET_ACCESS_KEY")
    app.config["AWS_REGION"] = os.getenv("AWS_REGION")
    app.config["S3_BUCKET_NAME"] = os.getenv("S3_BUCKET_NAME")


    if not app.config["MONGO_URI"]:
        raise ValueError("MONGO_URI missing in .env")

    # Mail Config
    app.config.update(
        MAIL_SERVER=os.getenv("MAIL_SERVER", "smtp.gmail.com"),
        MAIL_PORT=int(os.getenv("MAIL_PORT", 587)),
        MAIL_USE_TLS=os.getenv("MAIL_USE_TLS", "True").lower() == "true",
        MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
        MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
        MAIL_DEFAULT_SENDER=os.getenv("MAIL_DEFAULT_SENDER", os.getenv("MAIL_USERNAME"))
    )

    app.config["FRONTEND_URL"] = os.getenv("FRONTEND_URL")

    # Init extensions
    mongo.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)
    jwt.init_app(app)
    redis_client.init_app(app)

    allowed_origins = [
        app.config["FRONTEND_URL"],
    ]

    CORS(
        app,
        resources={r"/*": {"origins": allowed_origins}},
        supports_credentials=True
    )

    # Register Blueprints
    from routes.predict import predict_bp
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    app.register_blueprint(predict_bp, url_prefix="/predict")
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    from routes.admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix="/admin")
    from routes.admin_bootstrap import admin_bootstrap_bp
    app.register_blueprint(admin_bootstrap_bp)



    @app.route("/")
    def home():
        return {"msg": "API is running. Use /auth/login to authenticate."}


    return app
