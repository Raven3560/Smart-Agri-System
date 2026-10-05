"""
Train the extra-crops disease model: a small classifier on top of frozen image features.

Why this design
---------------
The PlantVillage MobileNetV2 already learned leaf colours, lesions and textures from
54,000 leaf photos. Its 1,280-number feature vector (the layer before its own 38-class
output) is reused as a fixed "leaf descriptor" for the new crops, and only a light
classifier is trained on top. This trains in minutes on a laptop CPU, needs only a few
hundred photos per class, and keeps live scanning fast because both models share the
same backbone.

Steps
-----
1. read data/agml_images/<crop>___<class>/ (made by ml/fetch_agml.py),
2. extract features once (original + mirror image, averaged), cache them,
3. split per class into train 70% / validation 15% / test 15% (fixed seed),
4. try logistic regression and a one-hidden-layer network with a few settings,
   pick the best on validation accuracy *within each crop*,
5. report test-set metrics, save the classifier as plain numpy arrays.

    python ml/train_extra.py
"""
import argparse
import datetime as dt
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

DATA = os.path.join(ROOT, "data", "agml_images")
OUT = os.path.join(ROOT, "models", "extra-crops")
CACHE = os.path.join(ROOT, "data", "agml_features.npz")


def list_images():
    classes = sorted(d for d in os.listdir(DATA) if os.path.isdir(os.path.join(DATA, d)) and "___" in d)
    paths, labels = [], []
    for i, c in enumerate(classes):
        for f in sorted(os.listdir(os.path.join(DATA, c))):
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                paths.append(os.path.join(DATA, c, f))
                labels.append(i)
    return classes, paths, np.array(labels)


def extract(paths, batch=48):
    import torch

    from agri.services.disease_model import DiseaseModel

    model = DiseaseModel(os.path.join(ROOT, "models", "plant-disease-mobilenetv2"))
    feats = []
    start = time.time()
    for i in range(0, len(paths), batch):
        ims = [Image.open(p).convert("RGB") for p in paths[i:i + batch]]
        f = model.features_batch(ims, tta=True)
        feats.append(f)
        done = min(i + batch, len(paths))
        rate = done / (time.time() - start)
        print(f"  features {done}/{len(paths)}  {rate:.0f} img/s", end=chr(13), flush=True)
    print()
    return np.concatenate(feats).astype(np.float32)


def split(labels, seed=42):
    rng = np.random.default_rng(seed)
    tr, va, te = [], [], []
    for c in np.unique(labels):
        idx = np.where(labels == c)[0]
        rng.shuffle(idx)
        n = len(idx)
        n_te, n_va = max(1, round(n * 0.15)), max(1, round(n * 0.15))
        te += list(idx[:n_te]); va += list(idx[n_te:n_te + n_va]); tr += list(idx[n_te + n_va:])
    return np.array(tr), np.array(va), np.array(te)


def crop_of(cls):
    return cls.split("___")[0]


def restricted_predict(proba, classes, true_labels):
    """Pick the best class among the true crop's classes (the app knows the crop)."""
    crops = np.array([crop_of(c) for c in classes])
    out = np.empty(len(true_labels), dtype=int)
    for i, t in enumerate(true_labels):
        mask = crops == crops[t]
        p = np.where(mask, proba[i], -1)
        out[i] = int(np.argmax(p))
    return out


def to_layers(clf, scaler):
    """Export a fitted sklearn model as plain arrays: standardise -> affine (-> relu -> affine)."""
    layers = {"mean": scaler.mean_.astype(np.float32), "scale": scaler.scale_.astype(np.float32)}
    if hasattr(clf, "coefs_"):
        layers["W0"], layers["b0"] = clf.coefs_[0].astype(np.float32), clf.intercepts_[0].astype(np.float32)
        layers["W1"], layers["b1"] = clf.coefs_[1].astype(np.float32), clf.intercepts_[1].astype(np.float32)
        layers["kind"] = np.array("mlp")
    else:
        layers["W0"], layers["b0"] = clf.coef_.T.astype(np.float32), clf.intercept_.astype(np.float32)
        layers["kind"] = np.array("linear")
    return layers


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true", help="re-extract features even if cached")
    ap.add_argument("--features-only", action="store_true", help="only extract and cache features")
    args = ap.parse_args()

    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import confusion_matrix, f1_score, precision_recall_fscore_support
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import StandardScaler

    classes, paths, labels = list_images()
    print(f"{len(paths)} images, {len(classes)} classes, {len({crop_of(c) for c in classes})} crops")
    # Feature cache keyed by image path, so new crops only need their own images processed.
    known = {}
    if os.path.exists(CACHE) and not args.refresh:
        cached = np.load(CACHE, allow_pickle=True)
        known = dict(zip(cached["paths"].tolist(), cached["X"]))
    missing = [p for p in paths if p not in known]
    if missing:
        print(f"extracting features for {len(missing)} new images ({len(paths) - len(missing)} cached)")
        for p, f in zip(missing, extract(missing)):
            known[p] = f
        np.savez_compressed(CACHE, X=np.stack([known[p] for p in paths]), paths=np.array(paths))
    X = np.stack([known[p] for p in paths]).astype(np.float32)
    if args.features_only:
        print("features cached; stopping (--features-only)")
        return

    tr, va, te = split(labels)
    scaler = StandardScaler().fit(X[tr])
    Xs = scaler.transform(X)

    candidates = [("logreg C=0.05", LogisticRegression(C=0.05, max_iter=4000)),
                  ("logreg C=0.2", LogisticRegression(C=0.2, max_iter=4000)),
                  ("logreg C=1", LogisticRegression(C=1.0, max_iter=4000)),
                  ("mlp 512", MLPClassifier(hidden_layer_sizes=(512,), alpha=1e-3, max_iter=300, early_stopping=True,
                                            random_state=0)),
                  ("mlp 512 strong-reg", MLPClassifier(hidden_layer_sizes=(512,), alpha=1e-2, max_iter=300,
                                                       early_stopping=True, random_state=0))]
    best = None
    for name, clf in candidates:
        t0 = time.time()
        clf.fit(Xs[tr], labels[tr])
        pred = restricted_predict(clf.predict_proba(Xs[va]), classes, labels[va])
        acc = float(np.mean(pred == labels[va]))
        print(f"  {name:20s} val accuracy (within crop) {acc:.4f}  [{time.time() - t0:.0f}s]")
        if best is None or acc > best[1]:
            best = (name, acc, clf)
    name, val_acc, clf = best
    print("selected:", name)

    # Final model: refit on train + validation, evaluate once on the untouched test split.
    trva = np.concatenate([tr, va])
    scaler = StandardScaler().fit(X[trva])
    Xs = scaler.transform(X)
    clf.fit(Xs[trva], labels[trva])
    proba = clf.predict_proba(Xs[te])
    pred = restricted_predict(proba, classes, labels[te])
    auto = np.argmax(proba, axis=1)
    y = labels[te]

    crops = sorted({crop_of(c) for c in classes})
    per_crop = {}
    for crop in crops:
        idx = [i for i, t in enumerate(y) if crop_of(classes[t]) == crop]
        cls_idx = [i for i, c in enumerate(classes) if crop_of(c) == crop]
        yt, yp = y[idx], pred[idx]
        p, r, f, s = precision_recall_fscore_support(yt, yp, labels=cls_idx, zero_division=0)
        per_crop[crop] = {
            "accuracy": round(float(np.mean(yt == yp)), 4),
            "macro_f1": round(float(np.mean(f)), 4),
            "test_images": len(idx),
            "classes": [{"key": classes[c], "precision": round(float(p[k]), 4), "recall": round(float(r[k]), 4),
                         "f1": round(float(f[k]), 4), "support": int(s[k])} for k, c in enumerate(cls_idx)],
            "confusion": confusion_matrix(yt, yp, labels=cls_idx).tolist(),
        }
    metrics = {
        "trained_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "backbone": "PlantVillage MobileNetV2 features (1280-d, mirror-averaged), frozen",
        "classifier": name,
        "images": len(paths), "train_images": int(len(trva)), "test_images": int(len(te)),
        "classes": len(classes), "crops": len(crops),
        "accuracy_within_crop": round(float(np.mean(pred == y)), 4),
        "macro_f1_within_crop": round(float(f1_score(y, pred, average="macro")), 4),
        "accuracy_auto_crop": round(float(np.mean(auto == y)), 4),
        "val_accuracy": round(val_acc, 4),
        "per_crop": per_crop,
        "note": ("Test images are a held-out 15% of each class that the classifier never saw. Some source datasets "
                 "contain several photos of the same leaf or augmented copies, which can make test scores optimistic."),
    }
    os.makedirs(OUT, exist_ok=True)
    np.savez(os.path.join(OUT, "head.npz"), **to_layers(clf, scaler))
    with open(os.path.join(OUT, "classes.json"), "w", encoding="utf-8") as fh:
        json.dump(classes, fh, indent=1)
    with open(os.path.join(OUT, "metrics.json"), "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=1)
    print(f"\nTest accuracy within crop: {metrics['accuracy_within_crop']:.4f} | macro F1 {metrics['macro_f1_within_crop']:.4f}"
          f" | auto-crop accuracy {metrics['accuracy_auto_crop']:.4f}")
    for crop, m in per_crop.items():
        print(f"  {crop:12s} acc {m['accuracy']:.3f}  macroF1 {m['macro_f1']:.3f}  (n={m['test_images']})")
    print("saved to", OUT)


if __name__ == "__main__":
    main()
