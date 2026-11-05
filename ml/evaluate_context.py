"""
Measure what the crop-context rule and the confidence levels add on top of the raw model.

Runs every image of a PlantVillage-style folder through the application's own interpretation
logic (agri/services/recommender.py), once with the correct crop selected and once with a
deliberately wrong crop, and writes the results next to the other evaluation files:

    <model>/evaluation/context.json

which the Model page shows.

Usage:
    python ml/fetch_sample.py --per-class 20 --out data/plantvillage_sample
    python ml/evaluate_context.py --data data/plantvillage_sample
"""
import argparse
import datetime as dt
import json
import os
import random
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PIL import Image  # noqa: E402

from agri.services import knowledge as kb  # noqa: E402
from agri.services import recommender  # noqa: E402
from agri.services.disease_model import DiseaseModel  # noqa: E402

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=os.path.join(ROOT, "data", "plantvillage_sample"))
    ap.add_argument("--model", default=os.path.join(ROOT, "models", "plant-disease-mobilenetv2"))
    ap.add_argument("--seed", type=int, default=7, help="seed for choosing the wrong crop")
    args = ap.parse_args()

    items = []
    for cls in sorted(os.listdir(args.data)):
        folder = os.path.join(args.data, cls)
        if not os.path.isdir(folder):
            continue
        truth = kb.disease_by_label(cls)
        if truth is None:
            print(f"skipping unknown class folder {cls}")
            continue
        for f in sorted(os.listdir(folder)):
            if os.path.splitext(f.lower())[1] in IMG_EXT:
                items.append((os.path.join(folder, f), truth))
    if not items:
        sys.exit(f"No images found in {args.data}")

    model = DiseaseModel(args.model)
    crops = sorted({t["crop"] for _, t in items})
    rng = random.Random(args.seed)
    n = len(items)
    no_ctx = ctx = 0
    levels = defaultdict(lambda: [0, 0])
    status = Counter()
    flagged = uncertain = capped = 0
    for i, (path, truth) in enumerate(items, 1):
        ranked = model.predict(Image.open(path).convert("RGB"))
        no_ctx += int(kb.disease_by_label(ranked[0][0])["key"] == truth["key"])
        r = recommender.interpret_prediction(ranked, truth["crop"])
        ok = r.get("disease") == truth["key"]
        ctx += int(ok)
        levels[r["level"]][0] += 1
        levels[r["level"]][1] += int(ok)
        status[r["status"]] += 1
        wrong = rng.choice([c for c in crops if c != truth["crop"]])
        w = recommender.interpret_prediction(ranked, wrong)
        flagged += int(w["mismatch"])
        uncertain += int(w["status"] == "uncertain")
        capped += int((w.get("crop_mass") or 1) < recommender.MIN_CROP_MASS)
        if i % 100 == 0:
            print(f"  {i}/{n} images")

    out = {
        "evaluated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "data_dir": os.path.relpath(os.path.abspath(args.data), ROOT),
        "images": n,
        "accuracy_without_context": round(no_ctx / n, 4),
        "accuracy_with_crop": round(ctx / n, 4),
        "levels": {k: {"images": v[0], "accuracy": round(v[1] / v[0], 4) if v[0] else None} for k, v in levels.items()},
        "status": dict(status),
        "wrong_crop": {"flagged_mismatch": round(flagged / n, 4), "reported_uncertain": round(uncertain / n, 4),
                       "crop_mass_below_15pct": round(capped / n, 4)},
    }
    path = os.path.join(args.model, "evaluation", "context.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(json.dumps(out, indent=2))
    print("saved", path)


if __name__ == "__main__":
    main()
