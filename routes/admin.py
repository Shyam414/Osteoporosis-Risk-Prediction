#admin.py
from flask import Blueprint, jsonify
from run import mongo
from bson import ObjectId
from utils.validators import admin, current_user_id
from utils.db_helpers import get_user_by_id, get_record_by_id, user_error_response,record_error_response
import gridfs

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
fs = gridfs.GridFS(mongo.db)


# ADMIN STATS
@admin_bp.route("/stats", methods=["GET"])
@admin
def admin_stats():
    return jsonify({
        "total_users": mongo.db.users.count_documents({}),
        "verified_users": mongo.db.users.count_documents({"verified": True}),
        "total_records": mongo.db.records.count_documents({})
    }), 200


# GET ALL USERS
@admin_bp.route("/users", methods=["GET"])
@admin
def all_users():
    users = []
    for u in mongo.db.users.find({}, {"password": 0}):
        u["_id"] = str(u["_id"])
        users.append(u)

    return jsonify(users), 200


# GET ALL RECORDS
@admin_bp.route("/records", methods=["GET"])
@admin
def all_records():
    records = []
    for r in mongo.db.records.find().sort("uploaded_at", -1):
        r["_id"] = str(r["_id"])
        records.append(r)

    return jsonify(records), 200


# DELETE ANY RECORD
@admin_bp.route("/records/<record_id>", methods=["DELETE"])
@admin
def delete_record(record_id):
    record, record_oid, error = get_record_by_id(record_id)

    if error:
        return record_error_response(error)

    if "file_id" in record:
        try:
            fs.delete(ObjectId(record["file_id"]))
        except Exception:
            pass

    mongo.db.records.delete_one({"_id": record_oid})

    return jsonify({"msg": "Record deleted successfully"}), 200


# DELETE USER + ALL RECORDS + ALL FILES
@admin_bp.route("/users/<user_id>", methods=["DELETE"])
@admin
def delete_user(user_id):
    user, user_oid, error = get_user_by_id(user_id)

    if error:
        return user_error_response(error)

    # SAFETY: prevent deleting admin users
    if user.get("role") == "admin":
        return jsonify({"msg": "Cannot delete admin user"}), 403

    # 1️ Find all records of this user
    records = mongo.db.records.find({"user_id": user_id})

    # 2️ Delete all files from GridFS
    for r in records:
        if "file_id" in r:
            try:
                fs.delete(ObjectId(r["file_id"]))
            except Exception:
                pass

    # 3️ Delete all records
    mongo.db.records.delete_many({"user_id": user_id})

    # 4️ Delete user
    mongo.db.users.delete_one({"_id": user_oid})

    return jsonify({
        "msg": "User and all associated records deleted successfully"
    }), 200


# VERIFY USER (ADMIN)
@admin_bp.route("/users/<user_id>/verify", methods=["POST"])
@admin
def verify_user(user_id):
    user, user_oid, error = get_user_by_id(user_id)

    if error:
        return user_error_response(error)

    if user.get("verified", False):
        return jsonify({"msg": "User already verified"}), 400

    mongo.db.users.update_one(
        {"_id": user_oid},
        {"$set": {"verified": True}}
    )

    return jsonify({"msg": "User verified successfully"}), 200


# PROMOTE USER TO ADMIN
@admin_bp.route("/users/<user_id>/promote", methods=["POST"])
@admin
def promote_user(user_id):
    user, user_oid, error = get_user_by_id(user_id)

    if error:
        return user_error_response(error)

    if not user.get("verified", False):
        return jsonify({"msg": "User must be verified first"}), 403

    if user.get("role") == "admin":
        return jsonify({"msg": "User is already an admin"}), 400

    mongo.db.users.update_one(
        {"_id": user_oid},
        {"$set": {"role": "admin"}}
    )

    return jsonify({"msg": "User promoted to admin"}), 200



@admin_bp.route("/users/<user_id>/demote", methods=["POST"])
@admin
def demote_user(user_id):
    user, user_oid, error = get_user_by_id(user_id)

    if error:
        return user_error_response(error)

    if user.get("role") != "admin":
        return jsonify({"msg": "User is not an admin"}), 400

    # prevent self-demotion
    if str(user_oid) == current_user_id():
        return jsonify({"msg": "You cannot demote yourself"}), 403

    admin_count = mongo.db.users.count_documents({"role": "admin"})
    if admin_count <= 1:
        return jsonify({"msg": "At least one admin required"}), 403

    mongo.db.users.update_one(
        {"_id": user_oid},
        {"$set": {"role": "user"}}
    )

    return jsonify({"msg": "Admin demoted"}), 200