import os
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


def download_model():
    os.makedirs(MODEL_DIR, exist_ok=True)

    if not os.path.exists(MODEL_PATH):
        if not MODEL_FILE_ID:
            raise RuntimeError("MODEL_FILE_ID not set in environment variables")

        print(" Downloading model from Google Drive...")
        gdown.download(
            id=MODEL_FILE_ID,
            output=MODEL_PATH,
            quiet=False
        )
        print(" Model downloaded")


def load_model():
    global model, device
    if model is not None:
        return model, device

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Download model if not present
    download_model()

    model = resnet50(weights=None)
    model.fc = nn.Linear(model.fc.in_features, 2)

    state_dict = torch.load(MODEL_PATH, map_location=device)
    model.load_state_dict(state_dict)

    model.to(device)
    model.eval()

    return model, device


# Preprocessing
infer_tf = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    ),
])

idx_to_label = {0: "Negative", 1: "Positive"}


@torch.inference_mode()
def predict_image(image_path):
    model, device = load_model()

    img = Image.open(image_path).convert("RGB")
    x = infer_tf(img).unsqueeze(0).to(device)

    logits = model(x)
    probs = F.softmax(logits, dim=1)[0]

    pred_idx = int(probs.argmax())
    return {
        "pred_label": idx_to_label[pred_idx],
        "pred_prob": round(float(probs[pred_idx] * 100), 2)
    }
