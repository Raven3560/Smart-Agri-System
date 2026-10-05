"""Main web pages of the Smart Agriculture Assistant."""
import datetime as dt
import json
import os
import uuid

from flask import (Blueprint, abort, current_app, flash, g, redirect, render_template, request,
                   send_from_directory, url_for)
from PIL import Image, ImageOps, UnidentifiedImageError

from . import db
from .auth import login_required
from .services import image_quality, irrigation, recommender, weather
from .services import knowledge as kb

bp = Blueprint("main", __name__)

DEFAULT_LOCATION = {"name": "Greater Noida, Uttar Pradesh, India", "lat": 28.4962, "lon": 77.536}
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
PAST_DAYS = 21  # weather history used by the water balance (one cache entry per location)

SAMPLES = [
    {"file": "tomato_late_blight.jpg", "crop": "tomato", "label": "Tomato, late blight"},
    {"file": "potato_early_blight.jpg", "crop": "potato", "label": "Potato, early blight"},
    {"file": "corn_common_rust.jpg", "crop": "maize", "label": "Maize, common rust"},
    {"file": "apple_scab.jpg", "crop": "apple", "label": "Apple, scab"},
    {"file": "grape_black_rot.jpg", "crop": "grape", "label": "Grape, black rot"},
    {"file": "pepper_bacterial_spot.jpg", "crop": "bell_pepper", "label": "Bell pepper, bacterial spot"},
    {"file": "tomato_healthy.jpg", "crop": "tomato", "label": "Tomato, healthy"},
    {"file": "money_plant_bacterial_wilt.jpg", "crop": "money_plant", "label": "Money plant, bacterial wilt"},
    {"file": "rice_blast.jpg", "crop": "rice", "label": "Rice, blast"},
    {"file": "mango_anthracnose.jpg", "crop": "mango", "label": "Mango, anthracnose"},
    {"file": "banana_sigatoka.jpg", "crop": "banana", "label": "Banana, sigatoka"},
    {"file": "groundnut_rust.jpg", "crop": "groundnut", "label": "Groundnut, rust"},
]


# --------------------------------------------------------------------------- helpers
def disease_model():
    return current_app.extensions["disease_model"]


def extra_model():
    return current_app.extensions["extra_model"]


def classify(image, crop_key):
    """Run the shared backbone once and use the model that covers this crop."""
    ranked_pv, feature = disease_model().analyse(image)
    if kb.model_for_crop(crop_key) == "extra" and extra_model().available:
        return extra_model().ranked(feature)
    return ranked_pv


def user_location():
    u = g.user
    if u is not None and u["lat"] is not None and u["lon"] is not None:
        return {"name": u["location_name"] or f"{u['lat']:.3f}, {u['lon']:.3f}", "lat": u["lat"], "lon": u["lon"],
                "is_default": False}
    return {**DEFAULT_LOCATION, "is_default": True}


def get_wx(lat, lon):
    return weather.get_weather(lat, lon, current_app.config["WEATHER_CACHE"], past_days=PAST_DAYS)


def fnum(name, default, lo=None, hi=None):
    try:
        value = float(request.form.get(name, default))
    except (TypeError, ValueError):
        value = float(default)
    if lo is not None:
        value = max(lo, value)
    if hi is not None:
        value = min(hi, value)
    return value


def form_location():
    """Location from the submitted form, falling back to the user's profile."""
    loc = user_location()
    try:
        lat = float(request.form.get("lat") or loc["lat"])
        lon = float(request.form.get("lon") or loc["lon"])
    except ValueError:
        lat, lon = loc["lat"], loc["lon"]
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        lat, lon = loc["lat"], loc["lon"]
    name = (request.form.get("location_name") or "").strip() or loc["name"]
    return {"name": name[:120], "lat": round(lat, 4), "lon": round(lon, 4)}


def farm_inputs():
    """Validated crop/farm inputs shared by the scan and irrigation forms."""
    crop = request.form.get("crop", "")
    stage = request.form.get("stage", "")
    soil = request.form.get("soil", "")
    method = request.form.get("method", "")
    errors = []
    if crop not in kb.crops():
        errors.append("Please choose a crop.")
    if stage not in kb.stages():
        errors.append("Please choose the growth stage.")
    if soil not in kb.soils():
        errors.append("Please choose the soil type.")
    if method not in kb.methods():
        errors.append("Please choose the irrigation method.")
    last = request.form.get("last_irrigation") or None
    if last:
        try:
            last_d = dt.date.fromisoformat(last)
            if last_d > dt.date.today():
                errors.append("Last irrigation date cannot be in the future.")
        except ValueError:
            errors.append("Last irrigation date is not valid.")
    return {
        "crop": crop, "stage": stage, "soil": soil, "method": method, "last_irrigation": last,
        "area_acres": fnum("area_acres", g.user["area_acres"] or 1, 0.01, 10000),
        "pump_hp": fnum("pump_hp", g.user["pump_hp"] or 5, 0.5, 100),
        "pump_head_m": fnum("pump_head_m", g.user["pump_head_m"] or 20, 3, 300),
        "tariff": fnum("tariff", g.user["tariff"] if g.user["tariff"] is not None else 6, 0, 100),
    }, errors


def form_defaults():
    u = g.user
    return {
        "crop": u["default_crop"] or "tomato", "stage": "mid", "soil": u["default_soil"] or "loamy",
        "method": u["default_method"] or "drip", "area_acres": u["area_acres"] or 1.0,
        "last_irrigation": (dt.date.today() - dt.timedelta(days=3)).isoformat(),
        "pump_hp": u["pump_hp"] or 5, "pump_head_m": u["pump_head_m"] or 20,
        "tariff": u["tariff"] if u["tariff"] is not None else 6, "location": user_location(),
    }


def run_irrigation(inputs, wx):
    return irrigation.plan_irrigation(
        crop_key=inputs["crop"], stage=inputs["stage"], soil_key=inputs["soil"], method_key=inputs["method"],
        area_acres=inputs["area_acres"], last_irrigation=inputs["last_irrigation"], weather=wx,
        pump_hp=inputs["pump_hp"], pump_head_m=inputs["pump_head_m"], tariff=inputs["tariff"],
    )


def chart_forecast(wx):
    days = wx["forecast"][:7]
    return {
        "labels": [dt.date.fromisoformat(d["date"]).strftime("%a %d") for d in days],
        "et0": [d["et0"] for d in days],
        "rain": [d["rain"] for d in days],
        "tmax": [d["tmax"] for d in days],
        "tmin": [d["tmin"] for d in days],
        "rain_prob": [d["rain_prob"] for d in days],
    }


# --------------------------------------------------------------------------- public pages
@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/project")
def project():
    return render_template("project.html")


@bp.route("/model")
def model_info():
    m = disease_model()
    metrics = None
    path = os.path.join(current_app.config["MODEL_DIR"], "evaluation", "metrics.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            metrics = json.load(fh)
    has_cm = os.path.exists(os.path.join(current_app.config["MODEL_DIR"], "evaluation", "confusion_matrix.png"))
    by_crop = {}
    for d in kb.diseases():
        by_crop.setdefault(d["crop"], []).append(d)
    extra = extra_model()
    extra_by_crop = {}
    for d in kb.extra_diseases():
        extra_by_crop.setdefault(d["crop"], []).append(d)
    sources_path = os.path.join(os.path.dirname(__file__), "data", "extra_sources.json")
    sources = []
    if os.path.exists(sources_path):
        with open(sources_path, encoding="utf-8") as fh:
            sources = json.load(fh)
    return render_template("model.html", info=m.info(), metrics=metrics, has_cm=has_cm, by_crop=by_crop,
                           extra_metrics=extra.metrics() if extra.available else None,
                           extra_by_crop=extra_by_crop, sources=sources)


@bp.route("/crops")
def crop_guide():
    entries = []
    for group, items in kb.crop_groups():
        for key, label in items:
            c = kb.crops()[key]
            entries.append({
                "key": key, "label": label, "group": group, "crop": c, "photo_check": key in kb.model_crops(),
                "houseplant": kb.is_houseplant(key), "problems": kb.crop_problems(key),
            })
    groups = [g for g, _ in kb.crop_groups()]
    return render_template("crops.html", entries=entries, groups=groups)


@bp.route("/model/confusion_matrix.png")
def confusion_matrix():
    return send_from_directory(os.path.join(current_app.config["MODEL_DIR"], "evaluation"), "confusion_matrix.png")


@bp.route("/healthz")
def healthz():
    m = disease_model()
    return {"status": "ok", "model_loaded": m.loaded, "model_error": m.load_error}


# --------------------------------------------------------------------------- dashboard
@bp.route("/dashboard")
@login_required
def dashboard():
    uid = g.user["id"]
    stats = db.query(
        "SELECT COUNT(*) AS scans,"
        " SUM(CASE WHEN status = 'diseased' THEN 1 ELSE 0 END) AS diseased,"
        " SUM(CASE WHEN status = 'healthy' THEN 1 ELSE 0 END) AS healthy"
        " FROM analyses WHERE user_id = ?", (uid,), one=True)
    plans = db.query(
        "SELECT COUNT(*) AS plans, COALESCE(SUM(water_saved_l), 0) AS water, COALESCE(SUM(energy_saved_kwh), 0) AS kwh"
        " FROM irrigation_plans WHERE user_id = ?", (uid,), one=True)
    recent = db.query("SELECT * FROM analyses WHERE user_id = ? ORDER BY id DESC LIMIT 4", (uid,))
    recent_plans = db.query("SELECT * FROM irrigation_plans WHERE user_id = ? ORDER BY id DESC LIMIT 3", (uid,))
    latest_plan = db.loads(recent_plans[0]["result_json"]) if recent_plans else None
    loc = user_location()
    wx = get_wx(loc["lat"], loc["lon"])
    return render_template(
        "dashboard.html", stats=stats, plans=plans, recent=recent, recent_plans=recent_plans,
        latest_plan=latest_plan, loc=loc, wx=wx, advisories=weather.farm_advisories(wx),
        chart=chart_forecast(wx),
        recent_disease={r["id"]: kb.disease_by_key(r["disease_key"]) for r in recent},
    )


# --------------------------------------------------------------------------- crop scan
@bp.route("/analyze", methods=["GET", "POST"])
@login_required
def analyze():
    supported, irrigation_only = kb.grouped_crop_choices()
    samples = [x for x in SAMPLES if os.path.exists(os.path.join(current_app.static_folder, "samples", x["file"]))]
    ctx = {"supported": supported, "irrigation_only": irrigation_only, "samples": samples,
           "model_crops": kb.model_crops()}
    if request.method == "GET":
        values = form_defaults()
        if request.args.get("crop") in kb.crops():
            values["crop"] = request.args["crop"]
        return render_template("analyze.html", values=values, **ctx)

    inputs, errors = farm_inputs()
    loc = form_location()
    upload = request.files.get("image")
    image = None
    if upload is None or not upload.filename:
        errors.append("Please upload or capture a photo of the crop.")
    else:
        ext = os.path.splitext(upload.filename.lower())[1]
        if ext and ext not in ALLOWED_EXT:
            errors.append("Please upload a JPG, PNG or WEBP image.")
        else:
            try:
                image = Image.open(upload.stream)
                image.load()
                image = ImageOps.exif_transpose(image).convert("RGB")
            except (UnidentifiedImageError, OSError):
                errors.append("The file could not be read as an image. If it is a HEIC photo, set the phone camera "
                              "to 'Most compatible' (JPG) or take a screenshot of it.")
    if errors:
        for e in errors:
            flash(e, "error")
        values = {**form_defaults(), **inputs, "location": loc}
        return render_template("analyze.html", values=values, **ctx), 400

    quality = image_quality.assess(image)
    prediction = None
    if inputs["crop"] in kb.model_crops():
        try:
            ranked = classify(image, inputs["crop"])
        except Exception:  # noqa: BLE001 - shown to the user as a friendly message
            current_app.logger.exception("Prediction failed")
            flash("The disease detection model could not be loaded. Run 'python scripts/download_model.py' "
                  "and restart the app.", "error")
            values = {**form_defaults(), **inputs, "location": loc}
            return render_template("analyze.html", values=values, **ctx), 500
        prediction = recommender.interpret_prediction(ranked, inputs["crop"])
    else:
        prediction = {"status": "unsupported", "crop_supported": False, "disease": None, "confidence": 0.0,
                      "level": "low", "top3": [], "mismatch": False, "adjusted": False, "raw_top": None,
                      "crop_mass": None}

    wx = get_wx(loc["lat"], loc["lon"])
    plan = run_irrigation(inputs, wx)
    report = recommender.build_report(prediction, inputs["crop"], inputs["stage"], wx, plan)

    filename = f"{uuid.uuid4().hex}.jpg"
    saved = image.copy()
    saved.thumbnail((1280, 1280))
    saved.save(os.path.join(current_app.config["UPLOAD_DIR"], filename), "JPEG", quality=88)

    payload = {
        "inputs": inputs, "location": loc, "quality": quality, "prediction": prediction, "report": report,
        "irrigation": plan,
        "weather": {"source": wx["source"], "current": wx["current"], "forecast": wx["forecast"][:5],
                    "fetched_at": wx.get("fetched_at")},
    }
    aid = db.execute(
        "INSERT INTO analyses (user_id, image_file, crop, stage, soil, location_name, lat, lon, status, disease_key,"
        " confidence, report_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (g.user["id"], filename, inputs["crop"], inputs["stage"], inputs["soil"], loc["name"], loc["lat"], loc["lon"],
         prediction["status"], prediction.get("disease"), prediction.get("confidence"), db.dumps(payload)),
    )
    return redirect(url_for("main.analysis", aid=aid))


def _own_analysis(aid):
    row = db.query("SELECT * FROM analyses WHERE id = ? AND user_id = ?", (aid, g.user["id"]), one=True)
    if row is None:
        abort(404)
    return row


@bp.route("/analysis/<int:aid>")
@login_required
def analysis(aid):
    row = _own_analysis(aid)
    data = db.loads(row["report_json"])
    return render_template("result.html", row=row, data=data, report=data["report"], pred=data["prediction"],
                           plan=data["irrigation"], disease=data["report"]["disease"])


@bp.route("/analysis/<int:aid>/delete", methods=["POST"])
@login_required
def delete_analysis(aid):
    row = _own_analysis(aid)
    db.execute("DELETE FROM analyses WHERE id = ?", (aid,))
    try:
        os.remove(os.path.join(current_app.config["UPLOAD_DIR"], row["image_file"]))
    except OSError:
        pass
    flash("Scan deleted.", "info")
    return redirect(url_for("main.history"))


@bp.route("/uploads/<path:name>")
@login_required
def uploaded(name):
    row = db.query("SELECT id FROM analyses WHERE image_file = ? AND user_id = ?", (name, g.user["id"]), one=True)
    if row is None:
        abort(404)
    return send_from_directory(current_app.config["UPLOAD_DIR"], name)


@bp.route("/live")
@login_required
def live():
    supported, _ = kb.grouped_crop_choices()
    meta = [{"key": d["key"], "name": d["name"], "crop": d["crop"], "crop_name": kb.crop_name(d["crop"]),
             "healthy": d["healthy"]} for d in kb.all_diseases()]
    return render_template("live.html", meta=meta, supported=supported, defaults=form_defaults())


# --------------------------------------------------------------------------- irrigation
@bp.route("/irrigation", methods=["GET", "POST"])
@login_required
def irrigation_planner():
    if request.method == "GET":
        values = form_defaults()
        if request.args.get("crop") in kb.crops():
            values["crop"] = request.args["crop"]
        return render_template("irrigation.html", values=values)

    inputs, errors = farm_inputs()
    loc = form_location()
    if errors:
        for e in errors:
            flash(e, "error")
        return render_template("irrigation.html", values={**form_defaults(), **inputs, "location": loc}), 400
    wx = get_wx(loc["lat"], loc["lon"])
    plan = run_irrigation(inputs, wx)
    plan["location"] = loc
    plan["weather"] = {"source": wx["source"], "fetched_at": wx.get("fetched_at")}
    pid = db.execute(
        "INSERT INTO irrigation_plans (user_id, crop, stage, soil, location_name, lat, lon, status, water_saved_l,"
        " energy_saved_kwh, result_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (g.user["id"], inputs["crop"], inputs["stage"], inputs["soil"], loc["name"], loc["lat"], loc["lon"],
         plan["status"], plan["savings"]["total_l"], plan["savings"]["total_kwh"], db.dumps(plan)),
    )
    return redirect(url_for("main.irrigation_plan", pid=pid))


def _own_plan(pid):
    row = db.query("SELECT * FROM irrigation_plans WHERE id = ? AND user_id = ?", (pid, g.user["id"]), one=True)
    if row is None:
        abort(404)
    return row


@bp.route("/irrigation/<int:pid>")
@login_required
def irrigation_plan(pid):
    row = _own_plan(pid)
    plan = db.loads(row["result_json"])
    template = "irrigation_result_pot.html" if plan.get("kind") == "houseplant" else "irrigation_result.html"
    return render_template(template, row=row, plan=plan)


@bp.route("/irrigation/<int:pid>/delete", methods=["POST"])
@login_required
def delete_plan(pid):
    _own_plan(pid)
    db.execute("DELETE FROM irrigation_plans WHERE id = ?", (pid,))
    flash("Irrigation plan deleted.", "info")
    return redirect(url_for("main.history", type="plans"))


# --------------------------------------------------------------------------- weather
@bp.route("/weather")
@login_required
def weather_page():
    loc = user_location()
    try:
        if request.args.get("lat") and request.args.get("lon"):
            lat, lon = float(request.args["lat"]), float(request.args["lon"])
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                loc = {"name": (request.args.get("name") or f"{lat:.3f}, {lon:.3f}")[:120], "lat": lat, "lon": lon,
                       "is_default": False}
    except ValueError:
        pass
    wx = get_wx(loc["lat"], loc["lon"])
    return render_template("weather.html", loc=loc, wx=wx, advisories=weather.farm_advisories(wx),
                           chart=chart_forecast(wx), spray=recommender.spray_advisory(wx))


# --------------------------------------------------------------------------- history
@bp.route("/history")
@login_required
def history():
    kind = request.args.get("type", "scans")
    crop = request.args.get("crop", "")
    status = request.args.get("status", "")
    uid = g.user["id"]
    if kind == "plans":
        sql, args = "SELECT * FROM irrigation_plans WHERE user_id = ?", [uid]
    else:
        kind = "scans"
        sql, args = "SELECT * FROM analyses WHERE user_id = ?", [uid]
    if crop in kb.crops():
        sql += " AND crop = ?"
        args.append(crop)
    if status:
        sql += " AND status = ?"
        args.append(status)
    rows = db.query(sql + " ORDER BY id DESC LIMIT 200", args)
    counts = {
        "scans": db.query("SELECT COUNT(*) AS n FROM analyses WHERE user_id = ?", (uid,), one=True)["n"],
        "plans": db.query("SELECT COUNT(*) AS n FROM irrigation_plans WHERE user_id = ?", (uid,), one=True)["n"],
    }
    diseases = {r["id"]: kb.disease_by_key(r["disease_key"]) for r in rows} if kind == "scans" else {}
    plan_data = {r["id"]: db.loads(r["result_json"]) for r in rows} if kind == "plans" else {}
    return render_template("history.html", rows=rows, kind=kind, crop=crop, status=status, counts=counts,
                           diseases=diseases, plan_data=plan_data)


# --------------------------------------------------------------------------- profile
@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if len(name) < 2:
            flash("Please enter your name.", "error")
            return redirect(url_for("main.profile"))
        lat = request.form.get("lat") or None
        lon = request.form.get("lon") or None
        try:
            lat = float(lat) if lat else None
            lon = float(lon) if lon else None
        except ValueError:
            lat = lon = None
        crop = request.form.get("default_crop")
        soil = request.form.get("default_soil")
        method = request.form.get("default_method")
        db.execute(
            "UPDATE users SET name = ?, phone = ?, farm_name = ?, location_name = ?, lat = ?, lon = ?,"
            " default_crop = ?, default_soil = ?, default_method = ?, area_acres = ?, pump_hp = ?, pump_head_m = ?,"
            " tariff = ? WHERE id = ?",
            (name, (request.form.get("phone") or "").strip(), (request.form.get("farm_name") or "").strip(),
             (request.form.get("location_name") or "").strip() or None, lat, lon,
             crop if crop in kb.crops() else "tomato", soil if soil in kb.soils() else "loamy",
             method if method in kb.methods() else "drip",
             fnum("area_acres", 1, 0.01, 10000), fnum("pump_hp", 5, 0.5, 100), fnum("pump_head_m", 20, 3, 300),
             fnum("tariff", 6, 0, 100), g.user["id"]),
        )
        flash("Profile saved.", "success")
        return redirect(url_for("main.dashboard"))
    return render_template("profile.html", welcome=request.args.get("welcome"))
