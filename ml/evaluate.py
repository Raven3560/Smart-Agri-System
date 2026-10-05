"""
Evaluate the crop disease model on a labelled image folder.

The folder must use the PlantVillage layout (one sub-folder per class, e.g.
``Tomato___Late_blight/``). Produces the metrics named in the synopsis
(Accuracy, Precision, Recall, F1-score and Confusion Matrix):

    <out>/metrics.json            overall + per-class metrics, timing, dataset info
    <out>/confusion_matrix.png    38 x 38 confusion matrix (row-normalised)
    <out>/classification_report.txt

Usage:
    python ml/evaluate.py --data data/plantvillage_sample
    python ml/evaluate.py --model models/my-model --data data/test --out models/my-model/evaluation
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

from agri.services import knowledge as kb  # noqa: E402
from agri.services.disease_model import DiseaseModel  # noqa: E402

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def short_name(d):
    crop = kb.crop_name(d["crop"]).split(" (")[0]
    name = d["name"]
    if d["healthy"]:
        return f"{crop}: healthy"
    for prefix in (crop + " ", "Maize ", "Bell Pepper ", "Citrus ", "Tomato "):
        if name.startswith(prefix):
            name = name[len(prefix):]
    return f"{crop}: {name}"


def collect(data_dir, model_labels):
    """Return [(path, true_index)] for every image whose folder maps to a model class."""
    label_index = {lab: i for i, lab in enumerate(model_labels)}
    samples, skipped = [], []
    for folder in sorted(os.listdir(data_dir)):
        full = os.path.join(data_dir, folder)
        if not os.path.isdir(full):
            continue
        d = kb.disease_by_label(folder)
        idx = None
        if folder in label_index:
            idx = label_index[folder]
        elif d is not None:
            for cand in (d["model_label"], d["pv_folder"], d["key"]):
                if cand in label_index:
                    idx = label_index[cand]
                    break
        if idx is None:
            skipped.append(folder)
            continue
        for name in sorted(os.listdir(full)):
            if os.path.splitext(name.lower())[1] in IMG_EXT:
                samples.append((os.path.join(full, name), idx))
    return samples, skipped


def plot_confusion(cm, names, path, title):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    # Single-hue sequential ramp (light -> dark blue).
    cmap = LinearSegmentedColormap.from_list("seq_blue", ["#f7fafd", "#cde2fb", "#86b6ef", "#2a78d6", "#104281"])
    with np.errstate(invalid="ignore", divide="ignore"):
        norm = cm / cm.sum(axis=1, keepdims=True)
    norm = np.nan_to_num(norm)
    n = len(names)
    fig, ax = plt.subplots(figsize=(max(8, n * 0.42), max(7, n * 0.4)), dpi=110)
    im = ax.imshow(norm, cmap=cmap, vmin=0, vmax=1)
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(names, rotation=90, fontsize=7)
    ax.set_yticklabels(names, fontsize=7)
    ax.set_xlabel("Predicted class")
    ax.set_ylabel("True class")
    ax.set_title(title, fontsize=11)
    for i in range(n):
        for j in range(n):
            if cm[i, j]:
                ax.text(j, i, int(cm[i, j]), ha="center", va="center", fontsize=6,
                        color="white" if norm[i, j] > 0.55 else "#0b0b0b")
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("Share of true class", fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def run_evaluation(model, samples, out, note="", data_desc="", batch=32):
    """Evaluate ``model`` (a DiseaseModel) on [(path, true_index)] and save all reports to ``out``."""
    from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix,
                                 precision_recall_fscore_support)

    os.makedirs(out, exist_ok=True)
    labels = model.labels
    y_true, y_pred, top3_hits = [], [], 0
    start = time.time()
    for i in range(0, len(samples), batch):
        chunk = samples[i:i + batch]
        images = [Image.open(p).convert("RGB") for p, _ in chunk]
        probs = model.predict_batch(images).numpy()
        for (_, t), pr in zip(chunk, probs):
            order = np.argsort(-pr)
            y_true.append(t)
            y_pred.append(int(order[0]))
            top3_hits += int(t in order[:3])
        print(f"  {min(i + batch, len(samples))}/{len(samples)}", end=chr(13))
    elapsed = time.time() - start
    print()

    classes = list(range(len(labels)))
    acc = accuracy_score(y_true, y_pred)
    present_true = sorted(set(y_true))
    p_m, r_m, f_m, _ = precision_recall_fscore_support(y_true, y_pred, labels=present_true, average="macro",
                                                       zero_division=0)
    p_w, r_w, f_w, _ = precision_recall_fscore_support(y_true, y_pred, labels=present_true, average="weighted",
                                                       zero_division=0)
    p_c, r_c, f_c, s_c = precision_recall_fscore_support(y_true, y_pred, labels=classes, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=classes)

    entries = [kb.disease_by_label(lab) for lab in labels]
    names = [short_name(d) if d else lab for d, lab in zip(entries, labels)]
    per_class = []
    for i in classes:
        if s_c[i] == 0:
            continue
        per_class.append({"id": i, "key": entries[i]["key"] if entries[i] else labels[i], "name": names[i],
                          "precision": round(float(p_c[i]), 4), "recall": round(float(r_c[i]), 4),
                          "f1": round(float(f_c[i]), 4), "support": int(s_c[i])})

    confusions = [{"true": names[i], "pred": names[j], "count": int(cm[i, j])}
                  for i in classes for j in classes if i != j and cm[i, j] > 0]
    confusions.sort(key=lambda c: -c["count"])

    metrics = {
        "evaluated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "model_dir": os.path.relpath(model.model_dir, ROOT),
        "data_dir": data_desc,
        "note": note,
        "images": len(samples),
        "classes": len(present_true),
        "accuracy": round(acc, 4),
        "top3_accuracy": round(top3_hits / len(samples), 4),
        "precision_macro": round(float(p_m), 4), "recall_macro": round(float(r_m), 4), "f1_macro": round(float(f_m), 4),
        "precision_weighted": round(float(p_w), 4), "recall_weighted": round(float(r_w), 4),
        "f1_weighted": round(float(f_w), 4),
        "ms_per_image_cpu": round(1000 * elapsed / len(samples), 1),
        "per_class": per_class,
        "top_confusions": confusions[:6],
    }
    with open(os.path.join(out, "metrics.json"), "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)
    present = sorted(set(y_true) | set(y_pred))
    report = classification_report(y_true, y_pred, labels=present, target_names=[names[i] for i in present],
                                   digits=4, zero_division=0)
    with open(os.path.join(out, "classification_report.txt"), "w", encoding="utf-8") as fh:
        fh.write(report)
    plot_confusion(cm, names, os.path.join(out, "confusion_matrix.png"),
                   f"Confusion matrix ({len(samples)} images, accuracy {acc:.1%})")
    print(report)
    print(f"Accuracy {acc:.4f} | Top-3 {metrics['top3_accuracy']:.4f} | Macro F1 {f_m:.4f} | "
          f"{metrics['ms_per_image_cpu']} ms/image on CPU")
    print("Saved results to", out)
    return metrics


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=os.path.join(ROOT, "models", "plant-disease-mobilenetv2"))
    ap.add_argument("--data", required=True, help="image folder in PlantVillage layout")
    ap.add_argument("--out", default=None, help="output folder (default: <model>/evaluation)")
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--note", default="", help="free-text note stored with the results")
    args = ap.parse_args()

    model = DiseaseModel(args.model)
    model.load()
    samples, skipped = collect(args.data, model.labels)
    if not samples:
        sys.exit("No images found that match the model's classes.")
    print(f"Evaluating {len(samples)} images across {len({s[1] for s in samples})} classes")
    if skipped:
        print("Skipped folders (no matching class):", ", ".join(skipped))
    run_evaluation(model, samples, args.out or os.path.join(args.model, "evaluation"), note=args.note,
                   data_desc=os.path.relpath(os.path.abspath(args.data), ROOT), batch=args.batch)


if __name__ == "__main__":
    main()
