import functools
import json
import logging
import os
import secrets

import bcrypt
from flask import jsonify, redirect, request, session, url_for


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_JSON_PATH = os.path.join(BASE_DIR, "config", "users.json")
SECRET_KEY_PATH = os.path.join(BASE_DIR, "config", "secret_key.txt")
SESSION_LIFETIME_HOURS = 8

logger = logging.getLogger(__name__)


def load_users() -> list[dict]:
    if not os.path.exists(USERS_JSON_PATH):
        logger.warning("Users config not found: %s", USERS_JSON_PATH)
        return []

    try:
        with open(USERS_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        logger.warning("Failed to load users config: %s", exc)
        return []

    users = data.get("users", [])
    return users if isinstance(users, list) else []


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def authenticate(login: str, password: str) -> dict | None:
    for user in load_users():
        if user.get("login") != login:
            continue
        if not verify_password(password, user.get("password_hash", "")):
            return None
        sanitized = dict(user)
        sanitized.pop("password_hash", None)
        return sanitized
    return None


def get_or_create_secret_key() -> str:
    if os.path.exists(SECRET_KEY_PATH):
        with open(SECRET_KEY_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()

    os.makedirs(os.path.dirname(SECRET_KEY_PATH), exist_ok=True)
    secret_key = secrets.token_hex(32)
    with open(SECRET_KEY_PATH, "w", encoding="utf-8") as f:
        f.write(secret_key)
    return secret_key


def _wants_json_response() -> bool:
    accept_header = request.headers.get("Accept", "")
    return request.is_json or "application/json" in accept_header


def login_required(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("login") is None:
            if _wants_json_response():
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return wrapper


def role_required(*roles):
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            if session.get("role") not in roles:
                return jsonify({"error": "Forbidden", "code": "FORBIDDEN"}), 403
            return f(*args, **kwargs)

        return wrapper

    return decorator


def current_user() -> dict:
    return {
        "login": session.get("login"),
        "display_name": session.get("display_name"),
        "role": session.get("role"),
    }
