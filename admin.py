#!/usr/bin/env python3
"""Simple Flask admin UI for the Raspberry Pi digital signage player."""

from __future__ import annotations

import json
import os
from functools import wraps
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from flask import Flask, Response, flash, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"


def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


CONFIG = load_config()
PLAYLIST_PATH = BASE_DIR / CONFIG.get("playlist_file", "playlist.json")
MEDIA_DIR = BASE_DIR / CONFIG.get("media_dir", "media")
ALLOWED_EXTENSIONS = {ext.lower() for ext in CONFIG.get("allowed_image_extensions", [])}

app = Flask(__name__)
app.secret_key = os.environ.get("SIGNAGE_FLASK_SECRET", "change-this-development-secret")


def get_admin_password() -> str | None:
    return os.environ.get("SIGNAGE_ADMIN_PASSWORD")


def load_playlist() -> list[dict[str, str]]:
    if not PLAYLIST_PATH.exists():
        return []
    with PLAYLIST_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return []
    cleaned: list[dict[str, str]] = []
    for item in data:
        if isinstance(item, dict) and item.get("type") in {"image", "url"} and item.get("source"):
            cleaned.append({"type": str(item["type"]), "source": str(item["source"])})
    return cleaned


def save_playlist(items: list[dict[str, str]]) -> None:
    tmp = PLAYLIST_PATH.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)
    tmp.replace(PLAYLIST_PATH)


def is_valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if session.get("authenticated"):
            return func(*args, **kwargs)
        return redirect(url_for("login"))

    return wrapper


@app.before_request
def restrict_to_local_network() -> Response | None:
    """Basic local-network guard. Use firewall/router rules for stronger protection."""
    remote = request.headers.get("X-Forwarded-For", request.remote_addr or "")
    remote = remote.split(",")[0].strip()
    local_prefixes = ("127.", "10.", "192.168.", "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.", "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.")
    if remote == "::1" or remote.startswith(local_prefixes):
        return None
    return Response("Admin UI is restricted to the local network.\n", status=403, mimetype="text/plain")


@app.route("/login", methods=["GET", "POST"])
def login():
    password = get_admin_password()
    if not password:
        flash("SIGNAGE_ADMIN_PASSWORD is not set. Set it in the systemd service environment.", "error")
    if request.method == "POST":
        if password and request.form.get("password") == password:
            session["authenticated"] = True
            return redirect(url_for("index"))
        flash("Incorrect password.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template(
        "index.html",
        playlist=load_playlist(),
        duration=CONFIG.get("global_duration_seconds", 15),
        fallback=CONFIG.get("fallback_image", "media/fallback.png"),
    )


@app.route("/add-url", methods=["POST"])
@login_required
def add_url():
    url = (request.form.get("url") or "").strip()
    if not is_valid_url(url):
        flash("Enter a valid http or https URL.", "error")
        return redirect(url_for("index"))
    playlist = load_playlist()
    playlist.append({"type": "url", "source": url})
    save_playlist(playlist)
    flash("URL added.", "success")
    return redirect(url_for("index"))


@app.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files.get("image")
    if not file or not file.filename:
        flash("Choose an image to upload.", "error")
        return redirect(url_for("index"))
    if not allowed_file(file.filename):
        flash("Unsupported image type.", "error")
        return redirect(url_for("index"))

    MEDIA_DIR.mkdir(exist_ok=True)
    filename = secure_filename(file.filename)
    target = MEDIA_DIR / filename
    stem, suffix = target.stem, target.suffix
    counter = 1
    while target.exists():
        target = MEDIA_DIR / f"{stem}-{counter}{suffix}"
        counter += 1

    file.save(target)
    playlist = load_playlist()
    playlist.append({"type": "image", "source": str(target.relative_to(BASE_DIR))})
    save_playlist(playlist)
    flash("Image uploaded and added to playlist.", "success")
    return redirect(url_for("index"))


@app.route("/move/<int:index>/<direction>", methods=["POST"])
@login_required
def move(index: int, direction: str):
    playlist = load_playlist()
    if direction == "up" and 0 < index < len(playlist):
        playlist[index - 1], playlist[index] = playlist[index], playlist[index - 1]
        save_playlist(playlist)
    elif direction == "down" and 0 <= index < len(playlist) - 1:
        playlist[index + 1], playlist[index] = playlist[index], playlist[index + 1]
        save_playlist(playlist)
    return redirect(url_for("index"))


@app.route("/delete/<int:index>", methods=["POST"])
@login_required
def delete(index: int):
    playlist = load_playlist()
    if 0 <= index < len(playlist):
        playlist.pop(index)
        save_playlist(playlist)
        flash("Item removed.", "success")
    return redirect(url_for("index"))


@app.route("/media/<path:filename>")
def media(filename: str):
    return send_from_directory(MEDIA_DIR, filename)


if __name__ == "__main__":
    app.run(host=CONFIG.get("admin_host", "0.0.0.0"), port=int(CONFIG.get("admin_port", 8080)))
