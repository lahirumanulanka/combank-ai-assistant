from mcp_server.data import EMPLOYEES, INCIDENT_RECORDS, SERVICES


def lookup_employee(name: str | None = None, team: str | None = None, on_call_for: str | None = None) -> list[dict]:
    return [
        employee for employee in EMPLOYEES
        if (name is None or name.lower() in employee["name"].lower())
        and (team is None or employee["team"] == team)
        and (on_call_for is None or on_call_for in employee["on_call_for"])
    ]


def get_service(name: str) -> dict:
    service = next((service for service in SERVICES if service["name"] == name), None)
    if service is None:
        return {"error": f"Unknown service '{name}'", "known_services": [s["name"] for s in SERVICES]}
    on_call = lookup_employee(on_call_for=name)
    return {**service, "on_call": [{"name": e["name"], "email": e["email"]} for e in on_call]}


def list_incident_records(service: str | None = None, severity: str | None = None,
                          since: str | None = None) -> dict:
    records = [
        record for record in INCIDENT_RECORDS
        if (service is None or record["service"] == service)
        and (severity is None or record["severity"] == severity)
        and (since is None or record["date"] >= since)
    ]
    return {"count": len(records), "total_minutes": sum(r["duration_min"] for r in records), "records": records}
