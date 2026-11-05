"""Fill a user account with example leaf checks and irrigation plans.

Useful before a presentation, so the dashboard, history and charts show real results with
today's weather. The account is created if it does not exist yet.

    python scripts/seed_account.py --email you@example.com --password "your-password" --name "Your Name"
    python scripts/seed_account.py --email you@example.com --password "your-password" --reset

--reset first deletes that account's existing scans and plans. Uses the real application
pipeline (disease models, weather API, irrigation engine), so it needs the model files and,
ideally, an internet connection.
"""
import argparse
import datetime as dt
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agri import create_app, db  # noqa: E402

SAMPLES = os.path.join(ROOT, "agri", "static", "samples")
TODAY = dt.date.today()
LOCATION = {"location_name": "Greater Noida, Uttar Pradesh, India", "lat": "28.4962", "lon": "77.536"}

SCANS = [  # file, crop, stage, soil, method, days since last irrigation
    ("tomato_healthy.jpg", "tomato", "development", "alluvial", "drip", 2),
    ("apple_scab.jpg", "apple", "mid", "loamy", "drip", 6),
    ("corn_common_rust.jpg", "maize", "mid", "alluvial", "furrow", 5),
    ("potato_early_blight.jpg", "potato", "development", "sandy_loam", "sprinkler", 4),
    ("rice_blast.jpg", "rice", "mid", "clay_loam", "flood", 3),
    ("mango_anthracnose.jpg", "mango", "mid", "alluvial", "drip", 5),
    ("banana_sigatoka.jpg", "banana", "mid", "loamy", "drip", 3),
    ("money_plant_bacterial_wilt.jpg", "money_plant", "mid", "loamy", "drip", 2),
    ("pepper_bacterial_spot.jpg", "bell_pepper", "mid", "loamy", "drip", 3),
    ("tomato_late_blight.jpg", "tomato", "mid", "alluvial", "drip", 4),
]
PLANS = [  # crop, stage, soil, method, days since last irrigation, acres
    ("wheat", "development", "alluvial", "flood", 9, 3.0),
    ("sugarcane", "mid", "alluvial", "furrow", 7, 2.5),
    ("tomato", "mid", "sandy", "drip", 6, 2.0),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--name", default="SmartAgri User", help="used only when the account is created")
    ap.add_argument("--farm", default="", help="farm name, used only when the account is created")
    ap.add_argument("--reset", action="store_true", help="delete this account's existing scans and plans first")
    args = ap.parse_args()
    email = args.email.strip().lower()

    app = create_app({"WTF_CSRF_ENABLED": False, "WARMUP_MODEL": False})
    client = app.test_client()
    with app.app_context():
        user = db.query("SELECT * FROM users WHERE email = ?", (email,), one=True)
    if user is None:
        r = client.post("/register", data={"name": args.name, "email": email, "phone": "", "farm_name": args.farm,
                                           "password": args.password, "confirm": args.password})
        if r.status_code != 302:
            sys.exit("Could not create the account. Use a valid e-mail and a password of at least 6 characters.")
        client.post("/profile", data={"name": args.name, "phone": "", "farm_name": args.farm, **LOCATION,
                                      "default_crop": "tomato", "default_soil": "alluvial", "default_method": "drip",
                                      "area_acres": "2", "pump_hp": "5", "pump_head_m": "20", "tariff": "6"})
        print("Created account", email)
    else:
        r = client.post("/login", data={"email": email, "password": args.password})
        if r.status_code != 302:
            sys.exit("Wrong password for this account.")
        if args.reset:
            with app.app_context():
                for row in db.query("SELECT image_file FROM analyses WHERE user_id = ?", (user["id"],)):
                    try:
                        os.remove(os.path.join(app.config["UPLOAD_DIR"], row["image_file"]))
                    except OSError:
                        pass
                db.execute("DELETE FROM analyses WHERE user_id = ?", (user["id"],))
                db.execute("DELETE FROM irrigation_plans WHERE user_id = ?", (user["id"],))
            print("Removed the existing scans and plans of", email)

    for crop, stage, soil, method, days, area in PLANS:
        r = client.post("/irrigation", data={
            "crop": crop, "stage": stage, "soil": soil, "method": method, "area_acres": area,
            "last_irrigation": (TODAY - dt.timedelta(days=days)).isoformat(), "pump_hp": 5, "pump_head_m": 20,
            "tariff": 6, **LOCATION})
        print("plan", crop, "ok" if r.status_code == 302 else r.status_code)
    for fname, crop, stage, soil, method, days in SCANS:
        with open(os.path.join(SAMPLES, fname), "rb") as fh:
            data = fh.read()
        r = client.post("/analyze", data={
            "crop": crop, "stage": stage, "soil": soil, "method": method, "area_acres": 2,
            "last_irrigation": (TODAY - dt.timedelta(days=days)).isoformat(), **LOCATION,
            "image": (io.BytesIO(data), fname)}, content_type="multipart/form-data")
        print("scan", fname, "ok" if r.status_code == 302 else r.status_code)
    print("Account ready:", email)


if __name__ == "__main__":
    main()
