from flask import Blueprint, current_app, jsonify

from run import mongo
from utils.validators import (
    login as login_required,
    current_user,
    current_user_oid,
)

admin_bootstrap_bp = Blueprint("admin_bootstrap", __name__)


@admin_bootstrap_bp.route("/admin/bootstrap", methods=["POST"])
@login_required
def bootstrap_admin():
    admin_email = current_app.config.get("ADMIN_EMAIL")

    if not admin_email:
        return jsonify({"msg": "ADMIN_EMAIL not configured"}), 500

    user = current_user()
    user_oid = current_user_oid()

    if not user.get("verified", False):
        return jsonify({"msg": "Email not verified"}), 403

    if user.get("role") == "admin":
        return jsonify({"msg": "Already an admin"}), 200

    if user["email"] != admin_email:
        return jsonify({"msg": "Not allowed to become admin"}), 403

    mongo.db.users.update_one(
        {"_id": user_oid},
        {"$set": {"role": "admin"}}
    )

    return jsonify({"msg": "Admin created successfully"}), 200