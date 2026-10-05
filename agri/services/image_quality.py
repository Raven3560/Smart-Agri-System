"""Basic image quality checks run before disease prediction.

The checks are intentionally simple and explainable:
* resolution  - very small images do not carry enough detail
* brightness  - mean grey level detects images that are too dark or washed out
* sharpness   - variance of the Laplacian; low values indicate a blurred photo
"""
import numpy as np
from PIL import Image

MIN_SIDE = 128
DARK_LIMIT = 45
BRIGHT_LIMIT = 225
BLUR_LIMIT = 20.0  # calibrated: <0.5% of PlantVillage images fall below; 2px Gaussian blur scores ~3-7


def laplacian_variance(gray: np.ndarray) -> float:
    g = gray.astype(np.float32)
    lap = (-4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:])
    return float(lap.var())


def assess(image: Image.Image) -> dict:
    width, height = image.size
    small = image.convert("L")
    small.thumbnail((512, 512))  # downscale only; upscaling would hide sharpness
    gray = np.asarray(small)
    brightness = float(gray.mean())
    sharpness = laplacian_variance(gray)

    issues = []
    if min(width, height) < MIN_SIDE:
        issues.append(f"The image is very small ({width}x{height} px). Use a photo at least {MIN_SIDE} px on each side.")
    if brightness < DARK_LIMIT:
        issues.append("The image is too dark. Take the photo in daylight or with better lighting.")
    elif brightness > BRIGHT_LIMIT:
        issues.append("The image is over-exposed. Avoid direct glare on the leaf.")
    if sharpness < BLUR_LIMIT:
        issues.append("The image looks blurred. Hold the camera steady and focus on the leaf.")

    return {
        "ok": not issues,
        "issues": issues,
        "width": width,
        "height": height,
        "brightness": round(brightness, 1),
        "sharpness": round(sharpness, 1),
    }


def plant_fraction(image: Image.Image) -> float:
    """Share of pixels that look like plant tissue (green, or yellow-brown leaf colour).

    Used by the live scanner to tell the user to point the camera at a leaf
    when the frame shows mostly walls, sky or hands. A soft hint only: a
    confident model prediction always takes priority.
    """
    small = image.convert("RGB").resize((96, 96))
    a = np.asarray(small).astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    spread = a.max(axis=2) - a.min(axis=2)
    green = (2 * g - r - b > 18) & (g > 40)
    yellow = (r > b + 40) & (g > b + 30) & (spread > 45) & (g > 70) & (g * 4 > r * 3)  # yellow, not brown wood
    return float((green | yellow).mean())
