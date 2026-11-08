import os

from mcp.server.fastmcp import FastMCP

from mcp_server import directory
from mcp_server.data import BANNER

mcp = FastMCP(
    "commbank-enterprise",
    instructions=f"Enterprise directory, service catalog and incident records. {BANNER}",
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("MCP_PORT", "8001")),
)


@mcp.tool()
def lookup_employee(name: str | None = None, team: str | None = None, on_call_for: str | None = None) -> list[dict]:
    """Find employees by part of their name, by team, or by the service they are on call for."""
    return directory.lookup_employee(name, team, on_call_for)


@mcp.tool()
def get_service(name: str) -> dict:
    """Get a service from the service catalog: owner team, tier, dependencies, related documents and who is on call."""
    return directory.get_service(name)


@mcp.tool()
def list_incident_records(service: str | None = None, severity: str | None = None, since: str | None = None) -> dict:
    """List structured incident records. Filter by service, severity (SEV1-SEV4) or since date (YYYY-MM-DD)."""
    return directory.list_incident_records(service, severity, since)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
