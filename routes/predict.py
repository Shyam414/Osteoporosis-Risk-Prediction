from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
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
@jwt_required()
def upload_file():
    user_id = get_jwt_identity()

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
    temp_path = os.path.join("temp_" + file.filename)
    with open(temp_path, "wb") as f:
        f.write(file_bytes)

    prediction = predict_image(temp_path)
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
@jwt_required()
def get_file(file_id):
    try:
        file = fs.get(ObjectId(file_id))
    except Exception:
        return jsonify({"msg": "File not found"}), 404
    return send_file(io.BytesIO(file.read()), mimetype=file.content_type)


# Retrieve File Metadata for Browser
@predict_bp.route("/file/<file_id>/meta", methods=["GET", "OPTIONS"])
@jwt_required(optional=True)  # allow OPTIONS without JWT
def get_file_meta(file_id):
    if request.method == "OPTIONS":
        return "", 200  # respond to preflight

    user_id = get_jwt_identity()
    if not user_id:
        return jsonify({"msg": "Missing or invalid token"}), 401

    record = mongo.db.records.find_one({"file_id": file_id, "user_id": user_id})
    if not record:
        return jsonify({"msg": "Record not found"}), 404

    return jsonify({
        "filename": record["filename"],
        "prediction": record["prediction"],
        "probability": record["probability"]
    }), 200


