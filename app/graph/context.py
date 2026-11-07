from dataclasses import dataclass

from app.core.rbac import Role


@dataclass(frozen=True)
class RuntimeContext:
    user_id: str
    role: Role
    name: str
