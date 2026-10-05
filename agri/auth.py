"""User registration and login."""
import functools
import re

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from . import DEMO_EMAIL, db

bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@bp.before_app_request
def load_user():
    uid = session.get("user_id")
    g.user = db.query("SELECT * FROM users WHERE id = ?", (uid,), one=True) if uid else None


def login_required(view):
    @functools.wraps(view)
    def wrapped(**kwargs):
        if g.user is None:
            flash("Please log in to continue.", "info")
            return redirect(url_for("auth.login", next=request.path))
        return view(**kwargs)

    return wrapped


def _safe_next(target):
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("main.dashboard")


def _login(user, remember=True):
    csrf = session.get("_csrf")
    session.clear()
    if csrf:
        session["_csrf"] = csrf
    session["user_id"] = user["id"]
    session.permanent = remember


@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("main.dashboard"))
    form = {"name": "", "email": "", "phone": "", "farm_name": ""}
    if request.method == "POST":
        form = {k: (request.form.get(k) or "").strip() for k in form}
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""
        errors = []
        if len(form["name"]) < 2:
            errors.append("Please enter your name.")
        if not EMAIL_RE.match(form["email"]):
            errors.append("Please enter a valid email address.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if not errors and db.query("SELECT id FROM users WHERE email = ?", (form["email"].lower(),), one=True):
            errors.append("An account with this email already exists. Please log in.")
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            uid = db.execute(
                "INSERT INTO users (name, email, password_hash, phone, farm_name) VALUES (?, ?, ?, ?, ?)",
                (form["name"], form["email"].lower(), generate_password_hash(password), form["phone"],
                 form["farm_name"]),
            )
            _login({"id": uid})
            flash("Welcome! Set your farm location so weather and irrigation advice match your field.", "success")
            return redirect(url_for("main.profile", welcome=1))
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("main.dashboard"))
    email = ""
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = db.query("SELECT * FROM users WHERE email = ?", (email,), one=True)
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Incorrect email or password.", "error")
        else:
            _login(user, remember=bool(request.form.get("remember")))
            return redirect(_safe_next(request.args.get("next")))
    return render_template("auth/login.html", email=email)


@bp.route("/demo", methods=["POST"])
def demo():
    user = db.query("SELECT * FROM users WHERE email = ?", (DEMO_EMAIL,), one=True)
    if user is None:
        flash("Demo account is not available.", "error")
        return redirect(url_for("auth.login"))
    _login(user)
    flash("You are using the demo account.", "info")
    return redirect(url_for("main.dashboard"))


@bp.route("/logout", methods=["POST"])
def logout():
    csrf = session.get("_csrf")
    session.clear()
    if csrf:
        session["_csrf"] = csrf
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))
