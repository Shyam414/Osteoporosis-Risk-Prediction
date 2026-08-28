import os
import threading

import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision.models import resnet50
from torchvision import transforms
from PIL import Image
import gdown


model, device = None, None
MODEL_DIR = "ml_models"
MODEL_PATH = os.path.join(MODEL_DIR, "knee_model2.pth")
MODEL_FILE_ID = os.environ.get("MODEL_FILE_ID")

# Prevent multiple threads from loading/downloading the model simultaneously
model_lock = threading.Lock()


def download_model():
    os.makedirs(MODEL_DIR, exist_ok=True)

    # Model already exists locally
    if os.path.exists(MODEL_PATH):
        return

    # MODEL_FILE_ID is missing
    if not MODEL_FILE_ID:
        raise RuntimeError(
            "MODEL_FILE_ID not set in environment variables"
        )

    print("Downloading model from Google Drive...")

    try:
        downloaded_file = gdown.download(
            id=MODEL_FILE_ID,
            output=MODEL_PATH,
            quiet=False
        )

        # Download failed
        if downloaded_file is None:
            raise RuntimeError(
                "Failed to download model from Google Drive. "
                "The file may not exist, the file ID may be invalid, "
                "or the file may not be publicly accessible."
            )

        # Verify model file exists
        if not os.path.exists(MODEL_PATH):
            raise RuntimeError(
                "Model download failed. "
                "The model file was not created."
            )

        print("Model downloaded successfully")

    except Exception as e:

        # Remove incomplete file if created
        if os.path.exists(MODEL_PATH):
            try:
                os.remove(MODEL_PATH)
            except OSError:
                pass

        raise RuntimeError(
            f"Unable to download model: {str(e)}"
        ) from e


def load_model():
    global model, device

    # Model already loaded
    if model is not None:
        return model, device

    # Only one thread can load the model
    with model_lock:

        # Check again after acquiring lock
        if model is not None:
            return model, device

        # Download model if not available locally
        download_model()

        # Select device
        device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        # Create ResNet50 model
        model = resnet50(weights=None)
        model.fc = nn.Linear(
            model.fc.in_features,
            2
        )

        # Load trained weights
        state_dict = torch.load(
            MODEL_PATH,
            map_location=device
        )

        model.load_state_dict(state_dict)

        # Move model to device
        model.to(device)
        model.eval()

    return model, device


# Image preprocessing
infer_tf = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    ),
])


idx_to_label = {
    0: "Negative",
    1: "Positive"
}


@torch.inference_mode()
def predict_image(image_path):

    global model, device
    if model is None:
        model, device = load_model()

    img = Image.open(image_path).convert("RGB")
    x = infer_tf(img).unsqueeze(0).to(device)
    logits = model(x)
    probs = F.softmax(logits, dim=1)[0]
    pred_idx = int(probs.argmax())

    return {
        "pred_label": idx_to_label[pred_idx],
        "pred_prob": round(
            float(probs[pred_idx] * 100),
            2
        )
    }