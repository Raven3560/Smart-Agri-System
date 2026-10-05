"""Extra-crops disease model (money plant, rice, sugarcane, cotton, mango, banana, ...).

A light classifier that sits on top of the PlantVillage MobileNetV2's 1,280-number
leaf descriptor (see ml/train_extra.py). The backbone runs once per photo and feeds
both the original 38-class model and this one, so adding crops costs almost no time.

The classifier is stored as plain numpy arrays (models/extra-crops/head.npz):
standardise -> affine -> (ReLU -> affine) -> softmax.
"""
import json
import os
import threading

import numpy as np


class ExtraModel:
    def __init__(self, model_dir):
        self.model_dir = model_dir
        self._head = None
        self._classes = None
        self._lock = threading.Lock()

    @property
    def available(self):
        return os.path.exists(os.path.join(self.model_dir, "head.npz")) and \
            os.path.exists(os.path.join(self.model_dir, "classes.json"))

    def _load(self):
        if self._head is not None:
            return
        with self._lock:
            if self._head is not None:
                return
            with np.load(os.path.join(self.model_dir, "head.npz")) as z:
                head = {k: z[k] for k in z.files}
            with open(os.path.join(self.model_dir, "classes.json"), encoding="utf-8") as fh:
                self._classes = json.load(fh)
            self._head = head

    @property
    def classes(self):
        if not self.available:
            return []
        self._load()
        return self._classes

    def crops(self):
        return sorted({c.split("___")[0] for c in self.classes})

    def probabilities(self, feature):
        """Class probabilities for one 1,280-number leaf descriptor."""
        self._load()
        h = self._head
        x = (np.asarray(feature, dtype=np.float32) - h["mean"]) / h["scale"]
        z = x @ h["W0"] + h["b0"]
        if str(h["kind"]) == "mlp":
            z = np.maximum(z, 0) @ h["W1"] + h["b1"]
        z = z - z.max()
        e = np.exp(z)
        return e / e.sum()

    def ranked(self, feature):
        p = self.probabilities(feature)
        return sorted(zip(self.classes, p.tolist()), key=lambda x: x[1], reverse=True)

    def metrics(self):
        path = os.path.join(self.model_dir, "metrics.json")
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
