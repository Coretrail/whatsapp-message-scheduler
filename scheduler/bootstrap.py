"""Initialise a local administrator; persist only salted password hashes."""
import hashlib
import json
import os
from pathlib import Path
import secrets


def load_config(path: Path) -> dict:
    path = Path(path)
    if path.exists():
        return json.loads(path.read_text())
    password = os.getenv('SCHEDULER_ADMIN_PASSWORD', '')
    username = os.getenv('SCHEDULER_ADMIN_USER', 'admin').strip()
    if len(password) < 12 or len(password) > 256 or not 1 <= len(username) <= 100:
        raise ValueError('Set an administrator username and a password of 12–256 characters')
    salt = secrets.token_hex(32)
    config = {'username': username, 'password_salt': salt,
              'password_hash': hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600000).hex()}
    path.parent.mkdir(parents=True, exist_ok=True)
    # Compose runs one API. Exclusive creation never resets an existing administrator.
    with open(path, 'x', opener=lambda name, flags: os.open(name, flags, 0o600)) as stream:
        json.dump(config, stream)
    return config
