from bson import ObjectId
from run import mongo
from flask import jsonify


def get_user_by_id(user_id):
    try:
        user_oid = ObjectId(user_id)
    except Exception:
        return None, None, "invalid"

    user = mongo.db.users.find_one({"_id": user_oid})

    if not user:
        return None, user_oid, "not_found"

    return user, user_oid, None


def get_record_by_id(record_id):
    try:
        record_oid = ObjectId(record_id)
    except Exception:
        return None, None, "invalid"

    record = mongo.db.records.find_one({"_id": record_oid})

    if not record:
        return None, record_oid, "not_found"

    return record, record_oid, None


def user_error_response(error):
    if error == "invalid":
        return jsonify({"msg": "Invalid user ID"}), 400

    if error == "not_found":
        return jsonify({"msg": "User not found"}), 404

    return None

def record_error_response(error):
    if error == "invalid":
        return jsonify({"msg": "Invalid record ID"}), 400

    if error == "not_found":
        return jsonify({"msg": "Record not found"}), 404