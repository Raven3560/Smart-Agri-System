"""Export the MobileNetV2 disease model to ONNX for lightweight hosting.

The ONNX graph returns both outputs the app needs from one pass:
  logits  (N, 38)    PlantVillage class scores
  pooled  (N, 1280)  leaf descriptor used by the extra-crops classifier

At run time the site then needs only onnxruntime + numpy (about 60 MB) instead of
PyTorch (800+ MB), which lets it run on Vercel and on 512 MB hosting plans.

    python scripts/export_onnx.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
import torch  # noqa: E402
from transformers import AutoModelForImageClassification  # noqa: E402

MODEL_DIR = os.path.join(ROOT, "models", "plant-disease-mobilenetv2")


class Both(torch.nn.Module):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, pixel_values):
        pooled = self.model.mobilenet_v2(pixel_values=pixel_values).pooler_output
        return self.model.classifier(pooled), pooled


def main():
    model = AutoModelForImageClassification.from_pretrained(MODEL_DIR).eval()
    wrapper = Both(model).eval()
    dummy = torch.randn(2, 3, 224, 224)
    out = os.path.join(MODEL_DIR, "model.onnx")
    torch.onnx.export(wrapper, (dummy,), out, input_names=["pixel_values"], output_names=["logits", "pooled"],
                      dynamic_axes={"pixel_values": {0: "batch"}, "logits": {0: "batch"}, "pooled": {0: "batch"}},
                      opset_version=17, dynamo=False)

    import onnxruntime as ort
    sess = ort.InferenceSession(out, providers=["CPUExecutionProvider"])
    x = np.random.default_rng(0).standard_normal((2, 3, 224, 224)).astype(np.float32)
    lo, po = sess.run(None, {"pixel_values": x})
    with torch.no_grad():
        lt, pt = wrapper(torch.from_numpy(x))
    print(f"saved {out} ({os.path.getsize(out) / 1e6:.1f} MB); max difference logits "
          f"{np.abs(lo - lt.numpy()).max():.2e}, pooled {np.abs(po - pt.numpy()).max():.2e}")


if __name__ == "__main__":
    main()
