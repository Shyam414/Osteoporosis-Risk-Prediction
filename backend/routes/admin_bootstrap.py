#admin_bootstrap.py
import os
from flask import Blueprint, jsonify
from run import mongo
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId

admin_bootstrap_bp = Blueprint("admin_bootstrap", __name__)


@admin_bootstrap_bp.route("/admin/bootstrap", methods=["POST"])
@jwt_required()
def bootstrap_admin():
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")

    if not ADMIN_EMAIL:
        return jsonify({"msg": "ADMIN_EMAIL not configured"}), 500

    user_id = get_jwt_identity()

    # Validate ObjectId
    try:
        user_oid = ObjectId(user_id)
    except Exception:
        return jsonify({"msg": "Invalid user identity"}), 401

    user = mongo.db.users.find_one({"_id": user_oid})

    if not user:
        return jsonify({"msg": "User not found"}), 404

    # Must be verified
    if not user.get("verified", False):
        return jsonify({"msg": "Email not verified"}), 403

    # Already admin
    if user.get("role") == "admin":
        return jsonify({"msg": "Already an admin"}), 200

    # Must match allowed admin email
    if user["email"] != ADMIN_EMAIL:
        return jsonify({"msg": "Not allowed to become admin"}), 403


    # Promote user
    mongo.db.users.update_one(
        {"_id": user_oid},
        {"$set": {"role": "admin"}}
    )

    return jsonify({"msg": "Admin created successfully"}), 200
