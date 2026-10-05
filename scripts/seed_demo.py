"""Reset the demo account and fill it with example scans and irrigation plans.

Run this shortly before a demo so the dashboard and history use fresh weather:
    python scripts/seed_demo.py

Uses the real application pipeline (disease model, weather API, irrigation
engine), so it needs the model files and, ideally, an internet connection.
"""
import datetime as dt
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agri import DEMO_EMAIL, create_app, db  # noqa: E402

SAMPLES = os.path.join(ROOT, "agri", "static", "samples")
TODAY = dt.date.today()

SCANS = [
    ("tomato_healthy.jpg", "tomato", "development", "alluvial", "drip", 2),
    ("apple_scab.jpg", "apple", "mid", "loamy", "drip", 6),
    ("corn_common_rust.jpg", "maize", "mid", "alluvial", "furrow", 5),
    ("potato_early_blight.jpg", "potato", "development", "sandy_loam", "sprinkler", 4),
    ("pepper_bacterial_spot.jpg", "bell_pepper", "mid", "loamy", "drip", 3),
    ("tomato_late_blight.jpg", "tomato", "mid", "alluvial", "drip", 4),
]
PLANS = [
    ("wheat", "development", "alluvial", "flood", 9, 3.0),
    ("tomato", "mid", "sandy", "drip", 6, 2.0),
]


def main():
    app = create_app({"WTF_CSRF_ENABLED": False, "WARMUP_MODEL": False})
    with app.app_context():
        user = db.query("SELECT * FROM users WHERE email = ?", (DEMO_EMAIL,), one=True)
        for row in db.query("SELECT image_file FROM analyses WHERE user_id = ?", (user["id"],)):
            try:
                os.remove(os.path.join(app.config["UPLOAD_DIR"], row["image_file"]))
            except OSError:
                pass
        db.execute("DELETE FROM analyses WHERE user_id = ?", (user["id"],))
        db.execute("DELETE FROM irrigation_plans WHERE user_id = ?", (user["id"],))
        loc = {"location_name": user["location_name"], "lat": user["lat"], "lon": user["lon"]}

    client = app.test_client()
    client.post("/demo")
    for crop, stage, soil, method, days, area in PLANS:
        r = client.post("/irrigation", data={
            "crop": crop, "stage": stage, "soil": soil, "method": method, "area_acres": area,
            "last_irrigation": (TODAY - dt.timedelta(days=days)).isoformat(), "pump_hp": 5, "pump_head_m": 20,
            "tariff": 6, **loc})
        print("plan", crop, r.status_code, r.headers.get("Location"))
    for fname, crop, stage, soil, method, days in SCANS:
        with open(os.path.join(SAMPLES, fname), "rb") as fh:
            data = fh.read()
        r = client.post("/analyze", data={
            "crop": crop, "stage": stage, "soil": soil, "method": method, "area_acres": 2,
            "last_irrigation": (TODAY - dt.timedelta(days=days)).isoformat(), **loc,
            "image": (io.BytesIO(data), fname)}, content_type="multipart/form-data")
        print("scan", fname, r.status_code, r.headers.get("Location"))
    print("Demo account ready:", DEMO_EMAIL)


if __name__ == "__main__":
    main()
