from flask import Blueprint, jsonify
from run import mongo
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId
from flask import request

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

@dashboard_bp.route("", methods=["GET", "OPTIONS"])
@jwt_required() 
def index():
    if request.method == "OPTIONS":
        return "", 200  # respond to preflight

    user_id = get_jwt_identity()
    if not user_id:
        return jsonify({"msg": "Missing or invalid token"}), 401

    try:
        user_id_obj = ObjectId(user_id)
    except Exception:
        return jsonify({"msg": "Invalid user ID"}), 400

    records = list(
        mongo.db.records.find({"user_id": user_id}).sort("uploaded_at", -1)
    )

    for r in records:
        r["_id"] = str(r["_id"])
        r["file_id"] = str(r["file_id"])

    user = mongo.db.users.find_one({"_id": user_id_obj}, {"email": 1})
    if not user:
        return jsonify({"msg": "User not found"}), 404

    return jsonify({
        "email": user["email"],
        "records": records if records else [],
        "msg": "MediLens API is running. Use /auth/login to authenticate."
    }), 200
