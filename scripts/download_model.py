"""Download the pretrained crop disease model into models/plant-disease-mobilenetv2.

Run once after installing requirements (needs internet). The web app also
downloads it automatically on first use if the folder is missing.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agri.services.disease_model import HF_REPO  # noqa: E402

if __name__ == "__main__":
    from transformers import AutoModelForImageClassification

    out = os.path.join(ROOT, "models", "plant-disease-mobilenetv2")
    print(f"Downloading {HF_REPO} ...")
    model = AutoModelForImageClassification.from_pretrained(HF_REPO)
    os.makedirs(out, exist_ok=True)
    model.save_pretrained(out)
    print(f"Saved {len(model.config.id2label)}-class model to {out}")
