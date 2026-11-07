from pathlib import Path

import bcrypt
import yaml

DEMO_USERS = [
    {"username": "viewer", "name": "Vimal Perera", "role": "viewer", "password": "viewer123"},
    {"username": "analyst", "name": "Anusha Silva", "role": "analyst", "password": "analyst123"},
    {"username": "admin", "name": "Ashan Fernando", "role": "admin", "password": "admin123"},
]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def main() -> None:
    users = [
        {
            "username": user["username"],
            "name": user["name"],
            "role": user["role"],
            "password_hash": hash_password(user["password"]),
        }
        for user in DEMO_USERS
    ]
    output = Path("data/users.yaml")
    output.write_text(yaml.safe_dump({"users": users}, sort_keys=False))
    print(f"Wrote {len(users)} users to {output}")


if __name__ == "__main__":
    main()
