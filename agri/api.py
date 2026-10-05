"""Small JSON API used by the front-end (location search, weather, live scanning)."""
import time

import requests
from flask import Blueprint, current_app, g, jsonify, request
from PIL import Image, UnidentifiedImageError

from .services import image_quality, weather
from .services import knowledge as kb

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.route("/geocode")
def geocode():
    if g.user is None:
        return jsonify({"error": "login required"}), 401
    try:
        return jsonify({"results": weather.geocode(request.args.get("q", ""))})
    except requests.RequestException:
        return jsonify({"results": [], "error": "Location search is unavailable. Check the internet connection "
                                                "or use 'My location'."}), 503


@bp.route("/weather")
def weather_json():
    if g.user is None:
        return jsonify({"error": "login required"}), 401
    try:
        lat, lon = float(request.args["lat"]), float(request.args["lon"])
    except (KeyError, ValueError):
        return jsonify({"error": "lat and lon are required"}), 400
    wx = weather.get_weather(lat, lon, current_app.config["WEATHER_CACHE"], past_days=21)
    return jsonify({"source": wx["source"], "current": wx["current"], "forecast": wx["forecast"]})


@bp.route("/live/predict", methods=["POST"])
def live_predict():
    """Classify one camera frame for the live scanner.

    The browser sends the square inside the on-screen guide box (about
    320 x 320 px) a few times per second. The response carries the probability
    of every class in knowledge-base order, so the page can smooth results
    across frames and apply the selected crop on its side.
    """
    if g.user is None:
        return jsonify({"error": "login required"}), 401
    frame = request.files.get("frame")
    if frame is None:
        return jsonify({"error": "no frame"}), 400
    try:
        img = Image.open(frame.stream)
        img.load()
        img = img.convert("RGB")
    except (UnidentifiedImageError, OSError):
        return jsonify({"error": "frame is not an image"}), 400
    img.thumbnail((640, 640))

    start = time.perf_counter()
    model = current_app.extensions["disease_model"]
    extra = current_app.extensions["extra_model"]
    try:
        ranked, feature = model.analyse(img)
        if extra.available:
            ranked = ranked + extra.ranked(feature)
    except Exception:  # noqa: BLE001 - reported to the page
        current_app.logger.exception("Live prediction failed")
        return jsonify({"error": "model unavailable"}), 503
    model_ms = (time.perf_counter() - start) * 1000

    # One probability per known class, in kb.all_diseases() order (PlantVillage, then extra crops).
    index = {d["key"]: i for i, d in enumerate(kb.all_diseases())}
    probs = [0.0] * len(index)
    for label, p in ranked:
        d = kb.disease_by_label(label)
        if d is not None and d["key"] in index:
            probs[index[d["key"]]] = round(float(p), 4)
    q = image_quality.assess(img)
    return jsonify({
        "probs": probs,
        "plant": round(image_quality.plant_fraction(img), 3),
        "quality": {"ok": q["ok"], "issues": q["issues"], "sharpness": q["sharpness"], "brightness": q["brightness"]},
        "model_ms": round(model_ms),
    })
