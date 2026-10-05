"""AI-Based Smart Agriculture Assistant for Crop Health and Smart Irrigation Management.

Flask application factory.
"""
import datetime as dt
import logging
import os
import secrets

from flask import Flask, abort, render_template, request, session
from werkzeug.security import generate_password_hash

from . import db
from .services import knowledge as kb
from .services.disease_model import DiseaseModel
from .services.extra_model import ExtraModel

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROJECT = {
    "title": "AI-Based Smart Agriculture Assistant for Crop Health and Smart Irrigation Management",
    "short": "SmartAgri AI",
    "college": "I.T.S Engineering College, Greater Noida",
    "department": "Department of Computer Science & Engineering",
    "university": "Dr. APJ Abdul Kalam Technical University, Lucknow",
    "session": "2026-27",
    "group": "27CSE53",
    "guide": "Mr. Sushil Chabbra",
    "guide_role": "Assistant Professor",
    "team": [
        {"name": "Pratyush Srivastava", "roll": "2302220100138"},
        {"name": "Rashmi Rajput", "roll": "2302220100145"},
        {"name": "Shivam Mahajan", "roll": "2302220100180"},
        {"name": "Shubham Kumar", "roll": "2302220100185"},
    ],
}

DEMO_EMAIL = "demo@smartagri.local"
DEMO_PASSWORD = "demo1234"


def _secret_key(instance_path):
    path = os.path.join(instance_path, "secret_key")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    key = secrets.token_hex(32)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(key)
    return key


def create_app(test_config=None):
    # INSTANCE_DIR lets a host (e.g. a Render persistent disk) keep the database and uploads across deploys.
    instance = os.environ.get("INSTANCE_DIR") or os.path.join(BASE_DIR, "instance")
    app = Flask(__name__, instance_path=instance, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)

    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY") or _secret_key(app.instance_path),
        DATABASE=os.path.join(app.instance_path, "smartagri.sqlite3"),
        UPLOAD_DIR=os.path.join(app.instance_path, "uploads"),
        WEATHER_CACHE=os.path.join(app.instance_path, "weather_cache"),
        MODEL_DIR=os.path.join(BASE_DIR, "models", "plant-disease-mobilenetv2"),
        MAX_CONTENT_LENGTH=12 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=dt.timedelta(days=14),
        WARMUP_MODEL=True,
        WTF_CSRF_ENABLED=True,
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    app.extensions["disease_model"] = DiseaseModel(app.config["MODEL_DIR"])
    app.extensions["extra_model"] = ExtraModel(os.path.join(BASE_DIR, "models", "extra-crops"))

    db.init_db(app)
    _ensure_demo_user(app)
    _register_template_helpers(app)
    _register_csrf(app)

    from .auth import bp as auth_bp
    from .views import bp as main_bp
    from .api import bp as api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("error.html", code=404, title="Page not found",
                               message="The page you were looking for does not exist."), 404

    @app.errorhandler(413)
    def too_large(_e):
        return render_template("error.html", code=413, title="Image too large",
                               message="Please upload an image smaller than 12 MB."), 413

    @app.errorhandler(400)
    def bad_request(e):
        return render_template("error.html", code=400, title="Request could not be processed",
                               message=getattr(e, "description", "Please go back and try again.")), 400

    if app.config.get("WARMUP_MODEL"):
        app.extensions["disease_model"].warmup_async()

    return app


def _ensure_demo_user(app):
    with app.app_context():
        if db.query("SELECT id FROM users WHERE email = ?", (DEMO_EMAIL,), one=True):
            return
        db.execute(
            "INSERT INTO users (name, email, password_hash, farm_name, location_name, lat, lon, default_crop,"
            " default_soil, default_method, area_acres, pump_hp, pump_head_m, tariff)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("Demo Farmer", DEMO_EMAIL, generate_password_hash(DEMO_PASSWORD), "Demo Farm",
             "Greater Noida, Uttar Pradesh, India", 28.4962, 77.536, "tomato", "alluvial", "drip", 2.0, 5.0, 20.0, 6.0),
        )


def _register_csrf(app):
    def csrf_token():
        if "_csrf" not in session:
            session["_csrf"] = secrets.token_urlsafe(32)
        return session["_csrf"]

    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def check_csrf():
        if not app.config.get("WTF_CSRF_ENABLED"):
            return
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
            if not sent or not secrets.compare_digest(sent, session.get("_csrf", "")):
                abort(400, description="Your session expired or the form was invalid. Please reload the page and try again.")


def _register_template_helpers(app):
    # Globals (not context) so that imported macros can use them too.
    app.jinja_env.globals.update(kb=kb, project=PROJECT)

    @app.context_processor
    def inject_globals():
        return {
            "now": dt.datetime.now(),
            "demo_email": DEMO_EMAIL,
            "demo_password": DEMO_PASSWORD,
        }

    @app.template_filter("crop_short")
    def crop_short(crop_key):
        return kb.crop_name(crop_key).split(" (")[0].lower()

    @app.template_filter("num")
    def num(value, digits=0):
        if value is None:
            return "-"
        try:
            value = float(value)
        except (TypeError, ValueError):
            return value
        if digits == 0:
            return f"{value:,.0f}"
        return f"{value:,.{digits}f}"

    @app.template_filter("litres")
    def litres(value):
        if value is None:
            return "-"
        value = float(value)
        if value >= 100000:
            return f"{value / 1000:,.0f} m³"
        if value >= 10000:
            return f"{value / 1000:,.1f} m³"
        return f"{value:,.0f} L"

    @app.template_filter("pct")
    def pct(value):
        if value is None:
            return "-"
        return f"{float(value) * 100:.0f}%"

    @app.template_filter("nicedate")
    def nicedate(value, fmt="%d %b %Y"):
        if not value:
            return "-"
        try:
            if len(str(value)) > 10:
                return dt.datetime.fromisoformat(str(value)).strftime(fmt + ", %I:%M %p")
            return dt.date.fromisoformat(str(value)).strftime(fmt)
        except ValueError:
            return value

    @app.template_filter("dayname")
    def dayname(value):
        try:
            d = dt.date.fromisoformat(str(value)[:10])
        except ValueError:
            return value
        today = dt.date.today()
        if d == today:
            return "Today"
        if d == today + dt.timedelta(days=1):
            return "Tomorrow"
        if d == today - dt.timedelta(days=1):
            return "Yesterday"
        return d.strftime("%a")
