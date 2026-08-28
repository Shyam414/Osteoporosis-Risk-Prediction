from flask import Blueprint, jsonify
from utils.validators import (
    login as login_required,
    current_user,
    current_user_id,
)
from utils.metadata_cache import get_dashboard_record_metadata
from services.s3_service import generate_presigned_url

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("", methods=["GET"])
@login_required
def index():

    user = current_user()
    user_id = current_user_id()

    # Redis holds MongoDB record metadata only. S3 URLs are generated below for
    # every response because they are temporary credentials, not cacheable data.
    records = get_dashboard_record_metadata(user_id)

    for record in records:

        record["_id"] = str(record["_id"])

        # Generate temporary S3 URL
        if "image_key" in record:

            record["image_url"] = generate_presigned_url(
                record["image_key"]
            )

    response = jsonify({

        "email": user["email"],

        "records": records,

        "msg": "Dashboard loaded successfully."

    })

    response.headers["Cache-Control"] = "private, max-age=60"

    return response, 200
