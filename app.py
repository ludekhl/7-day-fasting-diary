from __future__ import annotations
import os
import socket
import uuid
from datetime import date, datetime
from typing import List, Optional

from flask import (
    Flask, request, redirect, url_for, flash, send_from_directory, render_template
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask import session, g
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

# -------------------- Paths & App --------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_DIR = os.path.join(STATIC_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Ensure a base CSS exists (you can edit static/styles.css later)
STYLES_PATH = os.path.join(STATIC_DIR, "styles.css")
os.makedirs(STATIC_DIR, exist_ok=True)
if not os.path.exists(STYLES_PATH):
    with open(STYLES_PATH, "w", encoding="utf-8") as f:
        f.write(
            ":root{--bg:#f6f7fb;--ink:#0f172a;--card:#fff;--muted:#64748b;--ring:#eef2ff}"
            "body{background:var(--bg);color:var(--ink)}"
            ".glass{backdrop-filter:saturate(180%) blur(10px);background:rgba(255,255,255,.7)}"
            ".card{border:1px solid var(--ring)}"
            ".btn{box-shadow:0 1px 0 rgba(0,0,0,.02)}"
            ".brand{letter-spacing:.3px}"
        )

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "fasting_diary.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-me")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

db = SQLAlchemy(app)

# -------------------- Models --------------------
class Entry(db.Model):
    __tablename__ = "entries"
    id = db.Column(db.Integer, primary_key=True)
    when = db.Column(db.Date, nullable=False, index=True)
    day_number = db.Column(db.Integer, nullable=True)
    weight = db.Column(db.Float, nullable=True)
    energy = db.Column(db.Integer, nullable=True)     # 1–5
    water_ml = db.Column(db.Integer, nullable=True)
    mood = db.Column(db.String(32), nullable=True)
    feelings = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    photos = relationship("Photo", back_populates="entry", cascade="all, delete-orphan")


class Photo(db.Model):
    __tablename__ = "photos"
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(256), nullable=False)
    entry_id = db.Column(db.Integer, db.ForeignKey("entries.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    entry = relationship("Entry", back_populates="photos")

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    @staticmethod
    def create(username: str, password: str):
        u = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(u)
        db.session.commit()
        return u

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

with app.app_context():
    db.create_all()

@app.before_request
def load_user():
    uid = session.get("user_id")
    g.user = User.query.get(uid) if uid else None

@app.context_processor
def inject_auth():
    return {"logged_in": bool(g.user), "current_user": g.user}

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not g.user:
            flash("Please log in to do that.", "error")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapper

# -------------------- Helpers --------------------
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_files(files) -> List[str]:
    saved: List[str] = []
    for f in files:
        if not f or f.filename == "":
            continue
        if allowed_file(f.filename):
            ext = f.filename.rsplit(".", 1)[1].lower()
            name = f"{uuid.uuid4().hex}.{ext}"
            f.save(os.path.join(UPLOAD_DIR, name))
            saved.append(name)
        else:
            flash(f"Unsupported file type: {f.filename}", "error")
    return saved


def fast_start_date() -> date:
    val = os.environ.get("FAST_START_DATE")
    if val:
        try:
            return datetime.strptime(val, "%Y-%m-%d").date()
        except ValueError:
            pass
    first = Entry.query.order_by(Entry.when.asc()).first()
    return first.when if first else date.today()


def compute_day_number(d: date) -> int:
    return (d - fast_start_date()).days + 1


# -------------------- Routes --------------------
@app.route("/")
def dashboard():
    entries = Entry.query.order_by(Entry.when.asc()).all()
    labels = [e.when.strftime("%a %d %b") for e in entries]
    weights = [e.weight for e in entries]
    waters  = [e.water_ml for e in entries]          # <-- add
    energies = [e.energy for e in entries]           # <-- optional

    start = fast_start_date()
    today_num = compute_day_number(date.today())
    done_days = sum(1 for e in entries if 1 <= compute_day_number(e.when) <= 7)
    progress = min(100, max(0, int(done_days / 7 * 100)))
    return render_template(
        "dashboard.html",
        entries=entries,
        labels=labels,
        weights=weights,
        waters=waters,       # <-- add
        energies=energies,   # <-- add (optional)
        start=start,
        today_num=today_num,
        progress=progress,
    )

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session["user_id"] = user.id
            flash("Welcome back!", "success")
            nxt = request.args.get("next") or url_for("dashboard")
            return redirect(nxt)
        flash("Invalid credentials.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("dashboard"))

@app.route("/entries")
def list_entries():
    entries = Entry.query.order_by(Entry.when.desc()).all()
    return render_template("entries.html", entries=entries)


@app.route("/entry/new", methods=["GET", "POST"])
@app.route("/entry/<int:entry_id>/edit", methods=["GET", "POST"])
@login_required
def entry_form(entry_id: Optional[int] = None):
    entry = Entry.query.get(entry_id) if entry_id else None
    if request.method == "POST":
        when_str = request.form.get("when") or date.today().isoformat()
        when_d = datetime.strptime(when_str, "%Y-%m-%d").date()
        weight = float(request.form.get("weight")) if request.form.get("weight") else None
        energy = int(request.form.get("energy")) if request.form.get("energy") else None
        water_ml = int(request.form.get("water_ml")) if request.form.get("water_ml") else None
        mood = request.form.get("mood") or None
        feelings = request.form.get("feelings") or None

        if entry:
            entry.when = when_d
            entry.weight = weight
            entry.energy = energy
            entry.water_ml = water_ml
            entry.mood = mood
            entry.feelings = feelings
            entry.day_number = compute_day_number(when_d)
        else:
            entry = Entry(
                when=when_d,
                weight=weight,
                energy=energy,
                water_ml=water_ml,
                mood=mood,
                feelings=feelings,
                day_number=compute_day_number(when_d),
            )
            db.session.add(entry)
        db.session.commit()

        # Photos
        filenames = save_uploaded_files(request.files.getlist("photos"))
        for name in filenames:
            db.session.add(Photo(filename=name, entry_id=entry.id))
        db.session.commit()

        flash("Entry saved.", "success")
        return redirect(url_for("view_entry", entry_id=entry.id))

    return render_template("entry_form.html", entry=entry, today=date.today())


@app.route("/entry/<int:entry_id>")
def view_entry(entry_id: int):
    entry = Entry.query.get_or_404(entry_id)
    return render_template("entry_view.html", entry=entry)


@app.route("/entry/<int:entry_id>/delete", methods=["POST"])
@login_required
def delete_entry(entry_id: int):
    entry = Entry.query.get_or_404(entry_id)
    for p in entry.photos:
        try:
            os.remove(os.path.join(UPLOAD_DIR, p.filename))
        except OSError:
            pass
    db.session.delete(entry)
    db.session.commit()
    flash("Entry deleted.", "success")
    return redirect(url_for("list_entries"))


@app.route("/photo/<int:photo_id>/delete", methods=["POST"])
@login_required
def delete_photo(photo_id: int):
    photo = Photo.query.get_or_404(photo_id)
    try:
        os.remove(os.path.join(UPLOAD_DIR, photo.filename))
    except OSError:
        pass
    entry_id = photo.entry_id
    db.session.delete(photo)
    db.session.commit()
    flash("Photo removed.", "success")
    return redirect(url_for("view_entry", entry_id=entry_id))


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.errorhandler(413)
def too_large(e):
    flash("File too large.", "error")
    return redirect(request.referrer or url_for("dashboard"))


# -------------------- Run Helper --------------------
def find_free_port(start: int = 5000, limit: int = 20) -> int:
    for p in range(start, start + limit):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("0.0.0.0", p))
                return p
            except OSError:
                continue
    return start


if __name__ == "__main__":
    port = find_free_port(5000)
    print(f"* Starting on http://127.0.0.1:{port}")
    app.run(debug=True, host="0.0.0.0", port=port)