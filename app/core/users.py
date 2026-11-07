from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from app.core.config import get_settings
from app.core.rbac import Role
from app.core.security import verify_password


@dataclass(frozen=True)
class User:
    username: str
    name: str
    role: Role


@lru_cache
def _load_users() -> dict[str, dict]:
    path = Path(get_settings().users_file)
    data = yaml.safe_load(path.read_text())
    return {row["username"]: row for row in data["users"]}


def get_user(username: str) -> User | None:
    row = _load_users().get(username)
    if row is None:
        return None
    return User(username=row["username"], name=row["name"], role=Role(row["role"]))


def authenticate(username: str, password: str) -> User | None:
    row = _load_users().get(username)
    if row is None or not verify_password(password, row["password_hash"]):
        return None
    return get_user(username)
