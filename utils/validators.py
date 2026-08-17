# validators.py

from functools import wraps
from bson import ObjectId
from flask import g, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required
from run import mongo

def login(f):
    @wraps(f)
    @jwt_required()
    def decorated(*args, **kwargs):
        user_id = get_jwt_identity()

        try:
            user_oid = ObjectId(user_id)
        except Exception:
            return jsonify({"msg": "Invalid user identity"}), 401

        user = mongo.db.users.find_one({"_id": user_oid})

        if not user:
            return jsonify({"msg": "User not found"}), 404

        g.current_user = user
        g.current_user_id = user_id
        g.current_user_oid = user_oid

        return f(*args, **kwargs)

    return decorated


def refresh_login(f):
    @wraps(f)
    @jwt_required(refresh=True)
    def decorated(*args, **kwargs):
        return f(*args, **kwargs)

    return decorated


def optional_login(f):
    @wraps(f)
    @jwt_required(optional=True)
    def decorated(*args, **kwargs):
        user_id = get_jwt_identity()

        g.current_user = None
        g.current_user_id = None
        g.current_user_oid = None

        if user_id:
            try:
                user_oid = ObjectId(user_id)
                user = mongo.db.users.find_one({"_id": user_oid})

                if user:
                    g.current_user = user
                    g.current_user_id = user_id
                    g.current_user_oid = user_oid
            except Exception:
                pass

        return f(*args, **kwargs)

    return decorated


def admin(f):
    @login
    @wraps(f)
    def decorated(*args, **kwargs):
        if g.current_user.get("role") != "admin":
            return jsonify({"msg": "Admin access required"}), 403

        return f(*args, **kwargs)

    return decorated


def current_user():
    return g.current_user


def current_user_id():
    return g.current_user_id


def current_user_oid():
    return g.current_user_oid


