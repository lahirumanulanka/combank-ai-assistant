from enum import StrEnum


class Role(StrEnum):
    VIEWER = "viewer"
    ANALYST = "analyst"
    ADMIN = "admin"


ACCESS_LEVELS: dict[Role, list[str]] = {
    Role.VIEWER: ["public", "internal"],
    Role.ANALYST: ["public", "internal", "confidential"],
    Role.ADMIN: ["public", "internal", "confidential", "restricted"],
}


def allowed_access_levels(role: Role) -> list[str]:
    return ACCESS_LEVELS[role]
