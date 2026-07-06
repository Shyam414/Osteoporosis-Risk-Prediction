from flask import Blueprint, request, jsonify, send_file
from utils.validators import login as login_required, current_user_id
from run import mongo
from gridfs import GridFS
from bson import ObjectId
from datetime import datetime
import os, io
from services.ml_service import predict_image  

predict_bp = Blueprint("predict", __name__, url_prefix="/predict")
fs = GridFS(mongo.db)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


#Upload & Predict
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

    file_bytes = file.read()

    # Save file in GridFS
    file_id = fs.put(file_bytes, filename=file.filename, user_id=user_id, content_type=file.content_type)

    # Temporary save for ML prediction
    temp_path = f"temp_{file.filename}"

    try:
        with open(temp_path, "wb") as f:
            f.write(file_bytes)

        prediction = predict_image(temp_path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    record = {
        "user_id": user_id,
        "filename": file.filename,
        "prediction": prediction["pred_label"],
        "probability": prediction["pred_prob"],
        "file_id": str(file_id),
        "uploaded_at": datetime.utcnow()
    }
    mongo.db.records.insert_one(record)

    return jsonify(record), 201


# Retrieve File
@predict_bp.route("/file/<file_id>", methods=["GET"])
@login_required
def get_file(file_id):
    try:
        file = fs.get(ObjectId(file_id))
    except Exception:
        return jsonify({"msg": "File not found"}), 404
    response = send_file(
        io.BytesIO(file.read()),
        mimetype=file.content_type,
        max_age=86400  # 1 day
    )

    response.headers["Cache-Control"] = "public, max-age=86400"

    return response


# Retrieve File Metadata for Browser
@predict_bp.route("/file/<file_id>/meta", methods=["GET"])
@login_required
def get_file_meta(file_id):
    user_id = current_user_id()
    if not user_id:
        return jsonify({"msg": "Missing or invalid token"}), 401

    record = mongo.db.records.find_one({"file_id": file_id, "user_id": user_id})
    if not record:
        return jsonify({"msg": "Record not found"}), 404

    response = jsonify({
        "filename": record["filename"],
        "prediction": record["prediction"],
        "probability": record["probability"]
    })

    response.headers["Cache-Control"] = "private, max-age=3600"  # 1 hour

    return response, 200


