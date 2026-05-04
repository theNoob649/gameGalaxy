"""Game Galaxy - Flask backend.

Serves the game catalog, auth pages, and cloud-save endpoints.
"""

import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from hashlib import pbkdf2_hmac
from hmac import compare_digest

from flask import (
    Flask,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_ROOT, "game_galaxy.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "GAME_GALAXY_SECRET", "dev-secret-change-in-production"
)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


GAMES = [
    {
        "slug": "memory-match",
        "title": "Memory Match",
        "category": "Casual",
        "blurb": "Flip cards two at a time. Match every pair to win.",
        "color": "#ff6b9d",
    },
    {
        "slug": "tic-tac-toe",
        "title": "Tic Tac Toe",
        "category": "Strategy",
        "blurb": "Three in a row. Play a friend or beat the computer.",
        "color": "#4ecdc4",
    },
    {
        "slug": "snake",
        "title": "Snake",
        "category": "Arcade",
        "blurb": "Eat, grow, and don't hit yourself.",
        "color": "#a8e6cf",
    },
    {
        "slug": "twenty-forty-eight",
        "title": "2048",
        "category": "Puzzle",
        "blurb": "Slide and merge tiles to reach 2048.",
        "color": "#ffd166",
    },
    {
        "slug": "minesweeper",
        "title": "Minesweeper",
        "category": "Puzzle",
        "blurb": "Reveal the grid without clicking a mine.",
        "color": "#7dd3fc",
    },
    {
        "slug": "flap",
        "title": "Flap!",
        "category": "Reflex",
        "blurb": "Tap to fly. Don't hit the pipes.",
        "color": "#fcd34d",
    },
    {
        "slug": "runner",
        "title": "Sky Runner",
        "category": "Reflex",
        "blurb": "Run forever. Jump the obstacles.",
        "color": "#c084fc",
    },
    {
        "slug": "word-guess",
        "title": "Word Guess",
        "category": "Word",
        "blurb": "Guess today's 5-letter word in 6 tries.",
        "color": "#fb7185",
    },
    {
        "slug": "coal-clicker",
        "title": "Coal Clicker",
        "category": "Idle",
        "blurb": "Click coal. Buy upgrades. Watch the numbers go up forever.",
        "color": "#f97316",
    },
    {
        "slug": "lockpick",
        "title": "Lockpick",
        "category": "Timing",
        "blurb": "Time the spinning pin. Crack lock after lock.",
        "color": "#fbbf24",
    },
    {
        "slug": "color-switch",
        "title": "Color Switch",
        "category": "Reflex",
        "blurb": "Bounce upward. Match the ball's color through every obstacle.",
        "color": "#a78bfa",
    },
    {
        "slug": "stack-tower",
        "title": "Stack Tower",
        "category": "Reflex",
        "blurb": "Stack falling blocks. Land perfectly to keep going.",
        "color": "#60a5fa",
    },
    {
        "slug": "draw-guess",
        "title": "Drawing & Guess",
        "category": "Creative",
        "blurb": "Get a prompt. Draw it. Save it. No judging — just fun.",
        "color": "#34d399",
    },
    {
        "slug": "trivia",
        "title": "Trivia",
        "category": "Knowledge",
        "blurb": "Open Trivia DB questions across a dozen categories.",
        "color": "#fb923c",
    },
    {
        "slug": "whack-a-mole",
        "title": "Whack-a-Mole",
        "category": "Reflex",
        "blurb": "Hit the moles, miss the bombs. Gold ones are worth +5.",
        "color": "#a3e635",
    },
    {
        "slug": "color-echo",
        "title": "Color Echo",
        "category": "Memory",
        "blurb": "Watch the sequence of colored tones. Repeat it perfectly.",
        "color": "#22d3ee",
    },
    {
        "slug": "typing-race",
        "title": "Typing Race",
        "category": "Skill",
        "blurb": "Type the falling words before they hit the bottom.",
        "color": "#0ea5e9",
    },
    {
        "slug": "gem-swap",
        "title": "Gem Swap",
        "category": "Match Puzzle",
        "blurb": "Swap adjacent gems. Match 3+ to clear. Chain reactions multiply.",
        "color": "#ec4899",
    },
    {
        "slug": "bubble-shooter",
        "title": "Bubble Shooter",
        "category": "Match Puzzle",
        "blurb": "Aim, fire, connect. Pop 3+ bubbles of the same color.",
        "color": "#8b5cf6",
    },
    {
        "slug": "tower-defense",
        "title": "Tower Defense",
        "category": "Strategy",
        "blurb": "Place towers along the path. Survive 20 waves.",
        "color": "#dc2626",
    },
]

GAMES_BY_SLUG = {g["slug"]: g for g in GAMES}


# --- Database helpers ---

def get_db():
    db = getattr(g, "_db", None)
    if db is None:
        db = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        g._db = db
    return db


@app.teardown_appcontext
def close_db(_exception):
    db = getattr(g, "_db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL COLLATE NOCASE,
            email TEXT,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS saves (
            user_id INTEGER NOT NULL,
            game_slug TEXT NOT NULL,
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, game_slug),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS reset_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )
    db.commit()
    db.close()


# --- Auth helpers ---

def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    return digest.hex(), salt


def verify_password(password, stored_hash, salt):
    candidate, _ = hash_password(password, salt)
    return compare_digest(candidate, stored_hash)


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    row = get_db().execute(
        "SELECT id, username, email FROM users WHERE id = ?", (uid,)
    ).fetchone()
    return row


def login_required_json(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "auth_required"}), 401
        return view(*args, **kwargs)

    return wrapper


@app.context_processor
def inject_globals():
    return {"user": current_user(), "games": GAMES}


# --- Page routes ---

@app.route("/")
def home():
    return render_template("home.html")


@app.route("/play/<slug>")
def play(slug):
    game = GAMES_BY_SLUG.get(slug)
    if not game:
        abort(404)
    return render_template("game.html", game=game)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        email = (request.form.get("email") or "").strip() or None

        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template("signup.html", username=username, email=email or "")
        if len(username) < 3 or len(username) > 32:
            flash("Username must be 3-32 characters.", "error")
            return render_template("signup.html", username=username, email=email or "")
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("signup.html", username=username, email=email or "")

        db = get_db()
        existing = db.execute(
            "SELECT 1 FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            flash("That username is taken.", "error")
            return render_template("signup.html", username=username, email=email or "")

        pw_hash, salt = hash_password(password)
        db.execute(
            "INSERT INTO users (username, email, password_hash, password_salt, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (username, email, pw_hash, salt, datetime.utcnow().isoformat()),
        )
        db.commit()
        new_id = db.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()["id"]
        session["user_id"] = new_id
        flash("Welcome to Game Galaxy!", "success")
        return redirect(url_for("home"))

    return render_template("signup.html", username="", email="")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        row = get_db().execute(
            "SELECT id, password_hash, password_salt FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if not row or not verify_password(password, row["password_hash"], row["password_salt"]):
            flash("Wrong username or password.", "error")
            return render_template("login.html", username=username)
        session["user_id"] = row["id"]
        flash("Signed in.", "success")
        return redirect(url_for("home"))
    return render_template("login.html", username="")


@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    flash("Signed out.", "success")
    return redirect(url_for("home"))


@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        row = get_db().execute(
            "SELECT id, email FROM users WHERE username = ?", (username,)
        ).fetchone()
        if not row or not row["email"]:
            flash(
                "If an email is on file for that account, a reset link was sent. "
                "Accounts without an email cannot be recovered.",
                "info",
            )
            return render_template("forgot.html")

        token = secrets.token_urlsafe(32)
        expires = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        db = get_db()
        db.execute(
            "INSERT INTO reset_tokens (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, row["id"], expires),
        )
        db.commit()
        # Real deployment would email this. For now we surface it for development.
        reset_link = url_for("reset", token=token, _external=True)
        flash(f"Reset link generated: {reset_link}", "info")
        return render_template("forgot.html")
    return render_template("forgot.html")


@app.route("/reset/<token>", methods=["GET", "POST"])
def reset(token):
    db = get_db()
    row = db.execute(
        "SELECT user_id, expires_at FROM reset_tokens WHERE token = ?", (token,)
    ).fetchone()
    if not row or row["expires_at"] < datetime.utcnow().isoformat():
        flash("This reset link is invalid or has expired.", "error")
        return redirect(url_for("forgot"))

    if request.method == "POST":
        new_password = request.form.get("password") or ""
        if len(new_password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("reset.html", token=token)
        pw_hash, salt = hash_password(new_password)
        db.execute(
            "UPDATE users SET password_hash = ?, password_salt = ? WHERE id = ?",
            (pw_hash, salt, row["user_id"]),
        )
        db.execute("DELETE FROM reset_tokens WHERE token = ?", (token,))
        db.commit()
        flash("Password updated. You can sign in now.", "success")
        return redirect(url_for("login"))
    return render_template("reset.html", token=token)


# --- Cloud save API ---

@app.route("/api/saves", methods=["GET"])
@login_required_json
def list_saves():
    rows = get_db().execute(
        "SELECT game_slug, payload, updated_at FROM saves WHERE user_id = ?",
        (session["user_id"],),
    ).fetchall()
    return jsonify({
        "saves": {
            r["game_slug"]: {"payload": r["payload"], "updated_at": r["updated_at"]}
            for r in rows
        }
    })


@app.route("/api/saves/<slug>", methods=["GET"])
@login_required_json
def get_save(slug):
    row = get_db().execute(
        "SELECT payload, updated_at FROM saves WHERE user_id = ? AND game_slug = ?",
        (session["user_id"], slug),
    ).fetchone()
    if not row:
        return jsonify({"payload": None, "updated_at": None})
    return jsonify({"payload": row["payload"], "updated_at": row["updated_at"]})


@app.route("/api/saves/<slug>", methods=["PUT"])
@login_required_json
def put_save(slug):
    if slug not in GAMES_BY_SLUG:
        return jsonify({"error": "unknown_game"}), 400
    body = request.get_json(silent=True) or {}
    payload = body.get("payload")
    if not isinstance(payload, str) or len(payload) > 64_000:
        return jsonify({"error": "invalid_payload"}), 400
    db = get_db()
    db.execute(
        "INSERT INTO saves (user_id, game_slug, payload, updated_at)"
        " VALUES (?, ?, ?, ?)"
        " ON CONFLICT(user_id, game_slug) DO UPDATE SET"
        " payload = excluded.payload, updated_at = excluded.updated_at",
        (session["user_id"], slug, payload, datetime.utcnow().isoformat()),
    )
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/me")
def whoami():
    user = current_user()
    if not user:
        return jsonify({"signed_in": False})
    return jsonify({"signed_in": True, "username": user["username"]})


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
