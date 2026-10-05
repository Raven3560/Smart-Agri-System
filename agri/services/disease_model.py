"""Crop disease classifier (Computer Vision module).

Wraps a MobileNetV2 image classifier fine-tuned on the PlantVillage dataset
(38 classes across 14 crops). The model is stored in Hugging Face format under
``models/plant-disease-mobilenetv2``; any model trained with ``ml/train.py``
can be dropped into the same folder.
"""
import json
import logging
import os
import threading
import time

from PIL import Image

log = logging.getLogger(__name__)

HF_REPO = "linkanjarad/mobilenet_v2_1.0_224-plant-disease-identification"

# Same preprocessing the network was trained with: resize the short side to
# 256 px, centre-crop 224 x 224, scale to [0, 1], normalise with mean/std 0.5.
IMAGE_SIZE = 224
RESIZE_TO = 256
MEAN = [0.5, 0.5, 0.5]
STD = [0.5, 0.5, 0.5]


def load_preprocess(model_dir):
    """Normalisation settings saved next to the weights by ml/train.py (optional)."""
    path = os.path.join(model_dir, "preprocess.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            cfg = json.load(fh)
        return cfg.get("mean", MEAN), cfg.get("std", STD)
    return MEAN, STD


def build_transform(train=False, mean=MEAN, std=STD):
    from torchvision import transforms

    if train:
        return transforms.Compose([
            transforms.RandomResizedCrop(IMAGE_SIZE, scale=(0.7, 1.0)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomVerticalFlip(),
            transforms.RandomRotation(20),
            transforms.ColorJitter(0.2, 0.2, 0.2, 0.02),
            transforms.ToTensor(),
            transforms.Normalize(mean, std),
        ])
    return transforms.Compose([
        transforms.Resize(RESIZE_TO, interpolation=transforms.InterpolationMode.BILINEAR),
        transforms.CenterCrop(IMAGE_SIZE),
        transforms.ToTensor(),
        transforms.Normalize(mean, std),
    ])


class DiseaseModel:
    """Lazily loaded, thread-safe singleton around the classifier."""

    def __init__(self, model_dir):
        self.model_dir = model_dir
        self._model = None
        self._transform = None
        self._lock = threading.Lock()
        self.load_error = None
        self.load_seconds = None

    @property
    def loaded(self):
        return self._model is not None

    def load(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            start = time.time()
            try:
                import torch
                from transformers import AutoModelForImageClassification

                torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
                source = self.model_dir if os.path.isfile(os.path.join(self.model_dir, "config.json")) else HF_REPO
                if source == HF_REPO:
                    log.warning("Local model not found in %s; downloading %s", self.model_dir, HF_REPO)
                model = AutoModelForImageClassification.from_pretrained(source)
                model.eval()
                if source == HF_REPO:
                    os.makedirs(self.model_dir, exist_ok=True)
                    model.save_pretrained(self.model_dir)
                self._transform = build_transform(False, *load_preprocess(self.model_dir))
                self._model = model
                self.load_error = None
                self.load_seconds = round(time.time() - start, 1)
                log.info("Disease model loaded in %ss", self.load_seconds)
            except Exception as exc:  # noqa: BLE001 - surface any load failure to the UI
                self.load_error = str(exc)
                log.exception("Could not load disease model")
                raise
        return self._model

    @property
    def labels(self):
        model = self.load()
        return [model.config.id2label[i] for i in range(len(model.config.id2label))]

    def predict(self, image: Image.Image):
        """Return a list of (label, probability) for every class, best first."""
        import torch

        model = self.load()
        tensor = self._transform(image.convert("RGB")).unsqueeze(0)
        with torch.no_grad():
            probs = model(pixel_values=tensor).logits.softmax(-1)[0].tolist()
        labels = self.labels
        ranked = sorted(zip(labels, probs), key=lambda x: x[1], reverse=True)
        return ranked

    def predict_batch(self, images):
        import torch

        model = self.load()
        batch = torch.stack([self._transform(im.convert("RGB")) for im in images])
        with torch.no_grad():
            return model(pixel_values=batch).logits.softmax(-1)

    def features_batch(self, images, tta=False):
        """1280-number leaf descriptors from the layer before the classifier.

        With ``tta`` the mirror image is also passed through and the two
        descriptors are averaged, which makes them a little more robust.
        """
        import torch

        model = self.load()
        batch = torch.stack([self._transform(im.convert("RGB")) for im in images])
        with torch.no_grad():
            feats = model.mobilenet_v2(pixel_values=batch).pooler_output
            if tta:
                feats = (feats + model.mobilenet_v2(pixel_values=torch.flip(batch, dims=[3])).pooler_output) / 2
        return feats.numpy()

    def analyse(self, image):
        """One pass for both models: PlantVillage ranking plus the leaf descriptor.

        The mirror image is included so the descriptor matches how the extra-crops
        classifier was trained; PlantVillage probabilities come from the original view.
        """
        import torch

        model = self.load()
        x = self._transform(image.convert("RGB")).unsqueeze(0)
        batch = torch.cat([x, torch.flip(x, dims=[3])])
        with torch.no_grad():
            pooled = model.mobilenet_v2(pixel_values=batch).pooler_output
            probs = model.classifier(pooled[:1]).softmax(-1)[0].tolist()
        labels = self.labels
        ranked = sorted(zip(labels, probs), key=lambda x: x[1], reverse=True)
        return ranked, pooled.mean(0).numpy()

    def info(self):
        info = {"dir": self.model_dir, "loaded": self.loaded, "error": self.load_error,
                "load_seconds": self.load_seconds, "architecture": "MobileNetV2 (1.0, 224)",
                "source": HF_REPO, "input_size": f"{IMAGE_SIZE} x {IMAGE_SIZE} RGB"}
        weights = os.path.join(self.model_dir, "model.safetensors")
        if os.path.exists(weights):
            info["size_mb"] = round(os.path.getsize(weights) / 1e6, 1)
        if self.loaded:
            info["num_classes"] = len(self._model.config.id2label)
            info["parameters_m"] = round(sum(p.numel() for p in self._model.parameters()) / 1e6, 2)
        return info

    def warmup_async(self):
        def _run():
            try:
                self.load()
                self.predict(Image.new("RGB", (IMAGE_SIZE, IMAGE_SIZE), (90, 140, 70)))
            except Exception:  # noqa: BLE001
                pass

        threading.Thread(target=_run, name="model-warmup", daemon=True).start()
