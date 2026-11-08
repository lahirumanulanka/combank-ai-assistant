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


RESEARCH_ROLES = {Role.ANALYST, Role.ADMIN}


def can_research(role: Role) -> bool:
    return role in RESEARCH_ROLES


TOOL_ROLES: dict[str, set[Role]] = {
    "knowledge_search": {Role.VIEWER, Role.ANALYST, Role.ADMIN},
    "python_analysis": {Role.ANALYST, Role.ADMIN},
    "lookup_employee": {Role.ANALYST, Role.ADMIN},
    "get_service": {Role.ANALYST, Role.ADMIN},
    "list_incident_records": {Role.ANALYST, Role.ADMIN},
    "admin_purge_cache": {Role.ADMIN},
    "admin_reindex_namespace": {Role.ADMIN},
}

APPROVAL_TOOLS = {"admin_purge_cache", "admin_reindex_namespace"}
ROLE_ORDER = [Role.VIEWER, Role.ANALYST, Role.ADMIN]


def can_use_tool(role: Role, tool_name: str) -> bool:
    return role in TOOL_ROLES.get(tool_name, set())


def needs_approval(tool_name: str) -> bool:
    return tool_name in APPROVAL_TOOLS


def lowest_role_for(tool_name: str) -> Role | None:
    return next((role for role in ROLE_ORDER if role in TOOL_ROLES.get(tool_name, set())), None)
