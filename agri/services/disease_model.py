"""Crop disease classifier (Computer Vision module).

Wraps a MobileNetV2 image classifier fine-tuned on the PlantVillage dataset
(38 classes across 14 crops). The model is stored in Hugging Face format under
``models/plant-disease-mobilenetv2``; any model trained with ``ml/train.py``
can be dropped into the same folder.

Two interchangeable back ends:
  * "torch": Hugging Face / PyTorch (used for training and when PyTorch is installed),
  * "onnx":  ONNX Runtime with model.onnx (about 60 MB to install; used for hosting
             on Vercel or small plans). Create it with scripts/export_onnx.py.
The back end is picked automatically (PyTorch if it can be imported) or forced with
the environment variable SMARTAGRI_BACKEND=onnx|torch.
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


def preprocess_numpy(image, mean=MEAN, std=STD):
    """The same steps as build_transform(), using only PIL and numpy.

    torchvision resizes PIL images with the PIL bilinear filter and centre-crops with
    the same rounding, so both paths produce the same input.
    """
    import numpy as np

    im = image.convert("RGB")
    w, h = im.size
    if w <= h:
        size = (RESIZE_TO, int(RESIZE_TO * h / w))
    else:
        size = (int(RESIZE_TO * w / h), RESIZE_TO)
    im = im.resize(size, Image.BILINEAR)
    w, h = im.size
    top, left = int(round((h - IMAGE_SIZE) / 2.0)), int(round((w - IMAGE_SIZE) / 2.0))
    im = im.crop((left, top, left + IMAGE_SIZE, top + IMAGE_SIZE))
    x = np.asarray(im, dtype=np.float32) / 255.0
    x = (x - np.array(mean, dtype=np.float32)) / np.array(std, dtype=np.float32)
    return x.transpose(2, 0, 1)


def available_cpus():
    """CPU cores this process may really use.

    Containers (Render, Vercel, Docker) often report the host's core count while
    limiting the process to a fraction of one core through cgroups. Starting many
    threads there makes the model extremely slow, so read the real quota.
    """
    env = os.environ.get("SMARTAGRI_THREADS")
    if env and env.isdigit():
        return max(1, int(env))
    quota = None
    try:  # cgroup v2
        with open("/sys/fs/cgroup/cpu.max", encoding="utf-8") as fh:
            q, period = fh.read().split()[:2]
            if q != "max":
                quota = int(q) / int(period)
    except (OSError, ValueError):
        try:  # cgroup v1
            with open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us", encoding="utf-8") as fh:
                q = int(fh.read())
            with open("/sys/fs/cgroup/cpu/cpu.cfs_period_us", encoding="utf-8") as fh:
                period = int(fh.read())
            if q > 0:
                quota = q / period
        except (OSError, ValueError):
            pass
    cores = os.cpu_count() or 1
    if quota is not None:
        cores = min(cores, max(1, int(quota)))
    return max(1, min(4, cores))


def _softmax(z):
    import numpy as np

    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


class DiseaseModel:
    """Lazily loaded, thread-safe wrapper around the classifier."""

    def __init__(self, model_dir):
        self.model_dir = model_dir
        self._model = None
        self._session = None
        self._labels = None
        self._transform = None
        self._mean_std = (MEAN, STD)
        self._lock = threading.Lock()
        self._pid = os.getpid()
        self.backend = None
        self.load_error = None
        self.load_seconds = None
        self.stage = "not loaded"
        self.threads = None

    def _check_fork(self):
        """Web servers such as uWSGI and gunicorn fork worker processes. A model, thread
        pool or lock copied across a fork can hang forever, so start fresh in a new process."""
        if self._pid != os.getpid():
            self._pid = os.getpid()
            self._model = None
            self._session = None
            self._lock = threading.Lock()
            self.stage = "not loaded (new worker process)"

    @property
    def loaded(self):
        self._check_fork()
        return self._model is not None or self._session is not None

    @staticmethod
    def _choose_backend():
        forced = os.environ.get("SMARTAGRI_BACKEND", "").lower()
        if forced in ("onnx", "torch"):
            return forced
        try:
            import torch  # noqa: F401
            return "torch"
        except ImportError:
            return "onnx"

    def load(self):
        if self.loaded:
            return self._model or self._session
        # Never wait forever: if another request is stuck loading, fail with a clear message.
        if not self._lock.acquire(timeout=90):
            raise RuntimeError("The disease model is still loading. Please try again in a minute.")
        try:
            if self.loaded:
                return self._model or self._session
            start = time.time()
            try:
                self._mean_std = load_preprocess(self.model_dir)
                self.backend = self._choose_backend()
                if self.backend == "onnx":
                    self.stage = "importing onnxruntime"
                    import onnxruntime as ort

                    self.stage = "creating inference session"
                    opts = ort.SessionOptions()
                    # One thread by default: MobileNetV2 is small, and a single thread cannot
                    # deadlock after a fork or starve a small container. Override with SMARTAGRI_THREADS.
                    env_threads = os.environ.get("SMARTAGRI_THREADS", "")
                    self.threads = int(env_threads) if env_threads.isdigit() and int(env_threads) > 0 else 1
                    opts.intra_op_num_threads = self.threads
                    opts.inter_op_num_threads = 1
                    # Busy-waiting threads starve small containers; sleep instead.
                    opts.add_session_config_entry("session.intra_op.allow_spinning", "0")
                    opts.add_session_config_entry("session.inter_op.allow_spinning", "0")
                    self._session = ort.InferenceSession(os.path.join(self.model_dir, "model.onnx"), opts,
                                                         providers=["CPUExecutionProvider"])
                    with open(os.path.join(self.model_dir, "config.json"), encoding="utf-8") as fh:
                        id2label = json.load(fh)["id2label"]
                    self._labels = [id2label[str(i)] for i in range(len(id2label))]
                else:
                    self.stage = "importing torch"
                    import torch
                    from transformers import AutoModelForImageClassification

                    self.threads = available_cpus()
                    torch.set_num_threads(self.threads)
                    source = self.model_dir if os.path.isfile(os.path.join(self.model_dir, "config.json")) else HF_REPO
                    if source == HF_REPO:
                        log.warning("Local model not found in %s; downloading %s", self.model_dir, HF_REPO)
                    model = AutoModelForImageClassification.from_pretrained(source)
                    model.eval()
                    if source == HF_REPO:
                        os.makedirs(self.model_dir, exist_ok=True)
                        model.save_pretrained(self.model_dir)
                    self._transform = build_transform(False, *self._mean_std)
                    self._labels = [model.config.id2label[i] for i in range(len(model.config.id2label))]
                    self._model = model
                self.load_error = None
                self.load_seconds = round(time.time() - start, 1)
                self.stage = "ready"
                log.info("Disease model loaded (%s, %s threads) in %ss", self.backend, self.threads,
                         self.load_seconds)
            except Exception as exc:  # noqa: BLE001 - surface any load failure to the UI
                self.load_error = f"{type(exc).__name__}: {exc}"
                self.stage = "failed"
                log.exception("Could not load disease model")
                raise
        finally:
            self._lock.release()
        return self._model or self._session

    @property
    def labels(self):
        self.load()
        return self._labels

    def _forward(self, images, mirror=False):
        """(probabilities, pooled descriptors) as numpy arrays; with ``mirror`` the flipped images follow."""
        import numpy as np

        self.load()
        if self.backend == "onnx":
            x = np.stack([preprocess_numpy(im, *self._mean_std) for im in images]).astype(np.float32)
            if mirror:
                x = np.concatenate([x, x[:, :, :, ::-1]])
            logits, pooled = self._session.run(None, {"pixel_values": np.ascontiguousarray(x)})
            return _softmax(logits), pooled
        import torch

        x = torch.stack([self._transform(im.convert("RGB")) for im in images])
        if mirror:
            x = torch.cat([x, torch.flip(x, dims=[3])])
        with torch.no_grad():
            pooled = self._model.mobilenet_v2(pixel_values=x).pooler_output
            probs = self._model.classifier(pooled).softmax(-1)
        return probs.numpy(), pooled.numpy()

    def predict(self, image: Image.Image):
        """Return a list of (label, probability) for every class, best first."""
        probs, _ = self._forward([image])
        return sorted(zip(self.labels, probs[0].tolist()), key=lambda x: x[1], reverse=True)

    def predict_batch(self, images):
        probs, _ = self._forward(images)
        if self.backend == "torch":
            import torch
            return torch.from_numpy(probs)
        return probs

    def features_batch(self, images, tta=False):
        """1280-number leaf descriptors (mirror-averaged with ``tta``)."""
        _, pooled = self._forward(images, mirror=tta)
        if tta:
            n = len(images)
            pooled = (pooled[:n] + pooled[n:]) / 2
        return pooled

    def analyse(self, image):
        """One pass for both models: PlantVillage ranking plus the mirror-averaged leaf descriptor."""
        probs, pooled = self._forward([image], mirror=True)
        ranked = sorted(zip(self.labels, probs[0].tolist()), key=lambda x: x[1], reverse=True)
        return ranked, pooled.mean(0)

    def info(self):
        info = {"dir": self.model_dir, "loaded": self.loaded, "error": self.load_error,
                "load_seconds": self.load_seconds, "architecture": "MobileNetV2 (1.0, 224)",
                "source": HF_REPO, "input_size": f"{IMAGE_SIZE} x {IMAGE_SIZE} RGB", "backend": self.backend,
                "stage": self.stage, "threads": self.threads}
        for name in ("model.safetensors", "model.onnx"):
            weights = os.path.join(self.model_dir, name)
            if os.path.exists(weights):
                info["size_mb"] = round(os.path.getsize(weights) / 1e6, 1)
                break
        if self.loaded:
            info["num_classes"] = len(self._labels)
            info["parameters_m"] = (round(sum(p.numel() for p in self._model.parameters()) / 1e6, 2)
                                    if self._model is not None else 2.27)
        return info

    def warmup_async(self):
        def _run():
            try:
                self.load()
                self.predict(Image.new("RGB", (IMAGE_SIZE, IMAGE_SIZE), (90, 140, 70)))
            except Exception:  # noqa: BLE001
                pass

        threading.Thread(target=_run, name="model-warmup", daemon=True).start()
