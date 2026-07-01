from flask_jwt_extended import jwt_required, get_jwt_identity
from functools import wraps
from flask import jsonify
from bson import ObjectId
from run import mongo


def admin_required(f):
    @wraps(f)
    @jwt_required()
    def decorated_function(*args, **kwargs):
        user_id = get_jwt_identity()

        # Validate ObjectId
        try:
            user_oid = ObjectId(user_id)
        except Exception:
            return jsonify({"msg": "Invalid user identity"}), 401

        user = mongo.db.users.find_one(
            {"_id": user_oid},
            {"role": 1}
        )

        # User not found
        if not user:
            return jsonify({"msg": "User not found"}), 401

        # Not admin
        if user.get("role") != "admin":
            return jsonify({"msg": "Admin access required"}), 403

        return f(*args, **kwargs)

    return decorated_function
