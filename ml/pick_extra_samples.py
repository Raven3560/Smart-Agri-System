"""Copy a few correctly classified held-out photos of the new crops into agri/static/samples
for the "Try a sample leaf" buttons. Only CC BY 4.0 datasets are used for samples.

    python ml/pick_extra_samples.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "ml"))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from agri.services import recommender  # noqa: E402
from agri.services.disease_model import DiseaseModel  # noqa: E402
from agri.services.extra_model import ExtraModel  # noqa: E402
from train_extra import list_images, split  # noqa: E402

WANTED = {
    "money_plant___bacterial_wilt": "money_plant_bacterial_wilt.jpg",
    "rice___blast": "rice_blast.jpg",
    "mango___anthracnose": "mango_anthracnose.jpg",
    "banana___sigatoka": "banana_sigatoka.jpg",
    "groundnut___rust": "groundnut_rust.jpg",
}


def main():
    classes, paths, labels = list_images()
    _, _, test = split(labels)
    backbone = DiseaseModel(os.path.join(ROOT, "models", "plant-disease-mobilenetv2"))
    extra = ExtraModel(os.path.join(ROOT, "models", "extra-crops"))
    out_dir = os.path.join(ROOT, "agri", "static", "samples")
    for key, fname in WANTED.items():
        crop = key.split("___")[0]
        idx = [i for i in test if classes[labels[i]] == key]
        best = None
        for i in idx[:40]:
            img = Image.open(paths[i]).convert("RGB")
            _, feature = backbone.analyse(img)
            pred = recommender.interpret_prediction(extra.ranked(feature), crop)
            if pred["disease"] == key and (best is None or pred["confidence"] > best[1]):
                best = (i, pred["confidence"])
        if best is None:
            print("no correct sample for", key)
            continue
        img = Image.open(paths[best[0]]).convert("RGB")
        img.thumbnail((384, 384))
        img.save(os.path.join(out_dir, fname), "JPEG", quality=90)
        print(f"{fname}: {os.path.basename(paths[best[0]])} confidence {best[1]:.2f}")


if __name__ == "__main__":
    main()
