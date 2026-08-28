from flask import Blueprint, request, jsonify, current_app
from utils.validators import login as login_required, current_user_id
from run import mongo, limiter
from utils.metadata_cache import (
    invalidate_admin_stats,
    invalidate_dashboard_record_metadata,
)
from datetime import datetime
from services.ml_service import predict_image
from services.s3_service import (
    upload_file_to_s3,
    delete_file_from_s3,
    generate_presigned_url,
)
from PIL import Image, UnidentifiedImageError
import uuid
import os


predict_bp = Blueprint(
    "predict",
    __name__,
    url_prefix="/predict"
)


ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


def validate_image(file):
    try:
        image = Image.open(file.stream)
        image.verify()

        # Reset stream after verification
        file.stream.seek(0)

        return True

    except (
        UnidentifiedImageError,
        OSError,
        ValueError
    ):
        file.stream.seek(0)
        return False


# Upload Image + Run Prediction
@predict_bp.route("/upload", methods=["POST"])
@limiter.limit("10 per minute")
@login_required
def upload_file():

    user_id = current_user_id()

    if "file" not in request.files:
        return jsonify({
            "msg": "No file uploaded"
        }), 400

    file = request.files["file"]

    if not file.filename:
        return jsonify({
            "msg": "No selected file"
        }), 400

    if not allowed_file(file.filename):
        return jsonify({
            "msg": (
                "Invalid file type. "
                "Only JPG, JPEG and PNG files are allowed."
            )
        }), 400

    if not validate_image(file):
        return jsonify({
            "msg": "Invalid or corrupted image file"
        }), 400

    # Generate unique job ID
    job_id = str(uuid.uuid4())

    # Extract extension
    extension = file.filename.rsplit(
        ".",
        1
    )[1].lower()

    # S3 object key
    image_key = (
        f"users/{user_id}/{job_id}.{extension}"
    )

    # Temporary local file
    temp_file = (
        f"temp_{job_id}.{extension}"
    )

    uploaded_to_s3 = False

    try:
        # 1. Save uploaded image temporarily
        file.save(temp_file)

        # 2. Run ML prediction
        prediction = predict_image(
            temp_file
        )

        # 3. Upload image to S3
        upload_file_to_s3(
            temp_file,
            image_key
        )

        uploaded_to_s3 = True

        # 4. Create MongoDB metadata record
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

        # 5. Save record in MongoDB
        try:
            result = mongo.db.records.insert_one(
                record
            )

            record["_id"] = str(
                result.inserted_id
            )

        except Exception:
            current_app.logger.exception(
                "MongoDB insert failed"
            )

            # MongoDB failed after S3 upload
            # Delete orphaned S3 image
            if uploaded_to_s3:
                try:
                    delete_file_from_s3(
                        image_key
                    )

                    uploaded_to_s3 = False

                except Exception:
                    current_app.logger.exception(
                        "Failed to cleanup orphan S3 object"
                    )

            return jsonify({
                "msg": (
                    "Prediction could not be saved. "
                    "Please try again."
                )
            }), 500

        # 6. Invalidate Redis metadata cache
        try:
            invalidate_admin_stats()

            invalidate_dashboard_record_metadata(
                user_id
            )

        except Exception:
            # Redis is optional.
            # Prediction should still succeed.
            current_app.logger.warning(
                "Redis cache invalidation failed"
            )

        # 7. Generate temporary S3 access URL
        record["image_url"] = (
            generate_presigned_url(
                image_key
            )
        )

        return jsonify(record), 201

    except Exception:

        current_app.logger.exception(
            "Upload or prediction failed"
        )

        # If S3 succeeded but later processing failed,
        # delete the S3 object.
        if uploaded_to_s3:

            try:
                delete_file_from_s3(
                    image_key
                )

                uploaded_to_s3 = False

            except Exception:
                current_app.logger.exception(
                    "Failed to cleanup S3 object"
                )

        return jsonify({
            "msg": (
                "Upload or prediction failed. "
                "Please try again."
            )
        }), 500

    finally:
        # Always delete temporary local file
        if os.path.exists(temp_file):

            try:
                os.remove(temp_file)

            except OSError:
                current_app.logger.exception(
                    "Failed to remove temporary file"
                )


# Get Single Prediction
@predict_bp.route(
    "/result/<job_id>",
    methods=["GET"]
)
@login_required
def get_prediction(job_id):

    user_id = current_user_id()

    record = mongo.db.records.find_one({
        "job_id": job_id,
        "user_id": user_id
    })

    if not record:
        return jsonify({
            "msg": "Prediction not found"
        }), 404

    # Convert MongoDB ObjectId to string
    record["_id"] = str(
        record["_id"]
    )

    # Generate temporary S3 access URL
    record["image_url"] = (
        generate_presigned_url(
            record["image_key"]
        )
    )

    return jsonify(record), 200