from flask import Blueprint, request, jsonify
from utils.validators import login as login_required, current_user_id
from run import mongo
from utils.metadata_cache import (
    invalidate_admin_stats,
    invalidate_dashboard_record_metadata,
)
from datetime import datetime
from services.ml_service import predict_image
from services.s3_service import (
    upload_file_to_s3,
    download_file_from_s3,
    generate_presigned_url,
)
import uuid
import os

predict_bp = Blueprint("predict", __name__, url_prefix="/predict")

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


# ---------------------------------------------------
# Upload & Predict
# ---------------------------------------------------
@predict_bp.route("/upload", methods=["POST"])
@predict_bp.route("", methods=["POST"])
@predict_bp.route("/", methods=["POST"])
@login_required
def upload_file():

    user_id = current_user_id()

    if "file" not in request.files:
        return jsonify({"msg": "No file uploaded"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"msg": "No selected file"}), 400

    if not allowed_file(file.filename):
        return jsonify({"msg": "Invalid file type"}), 400

    job_id = str(uuid.uuid4())

    image_key = f"users/{user_id}/{job_id}_{file.filename}"

    # Upload to S3
    upload_file_to_s3(file, image_key)

    temp_file = f"temp_{job_id}.jpg"

    try:

        # Download from S3
        download_file_from_s3(image_key, temp_file)

        # Predict
        prediction = predict_image(temp_file)

    finally:

        if os.path.exists(temp_file):
            os.remove(temp_file)

    record = {

        "job_id": job_id,

        "user_id": user_id,

        "filename": file.filename,

        "image_key": image_key,

        "prediction": prediction["pred_label"],

        "probability": prediction["pred_prob"],

        "status": "completed",

        "uploaded_at": datetime.utcnow()

    }

    mongo.db.records.insert_one(record)
    invalidate_admin_stats()
    invalidate_dashboard_record_metadata(user_id)

    record["image_url"] = generate_presigned_url(image_key)

    return jsonify(record), 201


# ---------------------------------------------------
# Get Prediction
# ---------------------------------------------------
@predict_bp.route("/result/<job_id>", methods=["GET"])
@login_required
def get_prediction(job_id):

    user_id = current_user_id()

    record = mongo.db.records.find_one({
        "job_id": job_id,
        "user_id": user_id
    })

    if not record:
        return jsonify({"msg": "Prediction not found"}), 404

    record["_id"] = str(record["_id"])

    record["image_url"] = generate_presigned_url(
        record["image_key"]
    )

    return jsonify(record), 200
