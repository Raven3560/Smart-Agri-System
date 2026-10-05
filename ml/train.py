"""
Train (fine-tune) a crop disease classifier with transfer learning.

Dataset: PlantVillage in ImageFolder layout, one sub-folder per class, e.g.
    data/plantvillage/Tomato___Late_blight/*.jpg
Download it from Kaggle ("PlantVillage Dataset" or "New Plant Diseases Dataset")
or from https://github.com/spMohanty/PlantVillage-Dataset (raw/color).

The script:
  1. splits the images into train / validation / test sets (stratified, fixed seed),
  2. fine-tunes an ImageNet-pretrained backbone (MobileNetV2 by default; ResNet or
     EfficientNet also work) with data augmentation,
  3. keeps the checkpoint with the best validation accuracy,
  4. evaluates it on the held-out test set (accuracy, precision, recall, F1,
     confusion matrix) using ml/evaluate.py,
  5. saves everything in Hugging Face format so the web app can load it.

Examples:
    python ml/train.py --data data/plantvillage --epochs 5
    python ml/train.py --data data/plantvillage --base microsoft/resnet-50 --out models/resnet50-plant
    python ml/train.py --data data/plantvillage --base google/efficientnet-b0 --batch 32

To use the new model in the app, point MODEL_DIR at it (or copy it into
models/plant-disease-mobilenetv2). A GPU (for example Google Colab) is
recommended for the full dataset; on a CPU use --max-per-class to train on a subset.
"""
import argparse
import json
import os
import random
import sys
import time
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "ml"))

import torch  # noqa: E402
from PIL import Image  # noqa: E402
from torch.utils.data import DataLoader, Dataset  # noqa: E402

from agri.services.disease_model import MEAN, STD, DiseaseModel, build_transform  # noqa: E402

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


class Images(Dataset):
    def __init__(self, items, transform):
        self.items, self.transform = items, transform

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        path, label = self.items[i]
        return self.transform(Image.open(path).convert("RGB")), label


def split_dataset(data_dir, val=0.1, test=0.1, seed=42, max_per_class=None):
    classes = sorted(d for d in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, d)))
    rng = random.Random(seed)
    train, valid, testset = [], [], []
    for idx, cls in enumerate(classes):
        files = sorted(f for f in os.listdir(os.path.join(data_dir, cls)) if os.path.splitext(f.lower())[1] in IMG_EXT)
        rng.shuffle(files)
        if max_per_class:
            files = files[:max_per_class]
        paths = [(os.path.join(data_dir, cls, f), idx) for f in files]
        n_test = max(1, int(len(paths) * test))
        n_val = max(1, int(len(paths) * val))
        testset += paths[:n_test]
        valid += paths[n_test:n_test + n_val]
        train += paths[n_test + n_val:]
    return classes, train, valid, testset


def image_stats(base):
    """Normalisation used by the base model's own preprocessing."""
    try:
        from transformers import AutoImageProcessor

        proc = AutoImageProcessor.from_pretrained(base)
        return list(proc.image_mean), list(proc.image_std)
    except Exception:  # noqa: BLE001
        return MEAN, STD


def evaluate_loader(model, loader, device):
    model.eval()
    correct = total = 0
    loss_sum = 0.0
    with torch.no_grad():
        for x, y in loader:
            x, y = x.to(device), y.to(device)
            out = model(pixel_values=x).logits
            loss_sum += torch.nn.functional.cross_entropy(out, y, reduction="sum").item()
            correct += (out.argmax(-1) == y).sum().item()
            total += y.numel()
    return correct / max(total, 1), loss_sum / max(total, 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="PlantVillage folder (ImageFolder layout)")
    ap.add_argument("--base", default="google/mobilenet_v2_1.0_224", help="Hugging Face image classification checkpoint")
    ap.add_argument("--out", default=os.path.join(ROOT, "models", "my-plant-model"))
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--max-per-class", type=int, default=None, help="limit images per class (quick CPU runs)")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    from transformers import AutoModelForImageClassification

    torch.manual_seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    classes, train, valid, test = split_dataset(args.data, seed=args.seed, max_per_class=args.max_per_class)
    print(f"{len(classes)} classes | train {len(train)} | val {len(valid)} | test {len(test)} | device {device}")
    counts = defaultdict(int)
    for _, y in train:
        counts[y] += 1

    mean, std = image_stats(args.base)
    tr = DataLoader(Images(train, build_transform(True, mean, std)), batch_size=args.batch, shuffle=True,
                    num_workers=args.workers)
    va = DataLoader(Images(valid, build_transform(False, mean, std)), batch_size=args.batch, num_workers=args.workers)

    model = AutoModelForImageClassification.from_pretrained(
        args.base, num_labels=len(classes), id2label=dict(enumerate(classes)),
        label2id={c: i for i, c in enumerate(classes)}, ignore_mismatched_sizes=True,
    ).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    steps = args.epochs * len(tr)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=max(steps, 1), pct_start=0.15)

    os.makedirs(args.out, exist_ok=True)
    history, best = [], 0.0
    for epoch in range(1, args.epochs + 1):
        model.train()
        start, seen, correct, loss_sum = time.time(), 0, 0, 0.0
        for step, (x, y) in enumerate(tr, 1):
            x, y = x.to(device), y.to(device)
            logits = model(pixel_values=x).logits
            loss = torch.nn.functional.cross_entropy(logits, y, label_smoothing=0.1)
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
            seen += y.numel()
            correct += (logits.argmax(-1) == y).sum().item()
            loss_sum += loss.item() * y.numel()
            if step % 20 == 0:
                print(f"  epoch {epoch} step {step}/{len(tr)} loss {loss_sum / seen:.4f} acc {correct / seen:.4f}", end=chr(13))
        val_acc, val_loss = evaluate_loader(model, va, device)
        row = {"epoch": epoch, "train_loss": round(loss_sum / seen, 4), "train_acc": round(correct / seen, 4),
               "val_loss": round(val_loss, 4), "val_acc": round(val_acc, 4), "seconds": round(time.time() - start)}
        history.append(row)
        print(f"\nEpoch {epoch}: {row}")
        if val_acc >= best:
            best = val_acc
            model.save_pretrained(args.out)
            with open(os.path.join(args.out, "preprocess.json"), "w", encoding="utf-8") as fh:
                json.dump({"mean": mean, "std": std, "base": args.base}, fh, indent=2)
            print(f"  saved best model (val acc {best:.4f})")

    with open(os.path.join(args.out, "training_history.json"), "w", encoding="utf-8") as fh:
        json.dump({"base": args.base, "classes": classes, "history": history, "best_val_acc": best,
                   "train_images": len(train), "val_images": len(valid), "test_images": len(test)}, fh, indent=2)

    # Held-out test evaluation with the best checkpoint.
    from evaluate import run_evaluation

    best_model = DiseaseModel(args.out)
    best_model.load()
    run_evaluation(best_model, test, os.path.join(args.out, "evaluation"),
                   note=f"Held-out test split ({len(test)} images, {int(100 * 0.1)}% of each class) never used for "
                        f"training or model selection. Base model: {args.base}.",
                   data_desc=os.path.relpath(os.path.abspath(args.data), ROOT))


if __name__ == "__main__":
    main()
