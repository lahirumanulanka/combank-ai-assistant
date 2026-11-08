def _ids(chunk_ids: list[str]) -> str:
    return ", ".join(f"`{chunk_id}`" for chunk_id in chunk_ids)


def _supervisor(data: dict) -> tuple[str, str]:
    detail = f"route **{data['route']}** - {data['rationale']}  \nsearch: _{data['search_query']}_"
    if data.get("downgraded"):
        detail += "  \n:orange[research needs the analyst role - answering from top passages]"
    return "Supervisor", detail


def _research_plan(data: dict) -> tuple[str, str]:
    return "Research planner", f"{data['rationale']}\n```python\n{data['code']}\n```"


def _research_execute(data: dict) -> tuple[str, str]:
    groups = "  \n".join(f"batch {i}: {_ids(group)}" for i, group in enumerate(data["batches"], start=1))
    return "Sandbox ran the plan", f"{data['source']} - **{len(data['batches'])}** batches  \n{groups}"


def _research_worker(data: dict) -> tuple[str, str]:
    detail = f"analysed {_ids(data['analysed']) or 'nothing'}"
    if data["errors"]:
        detail += f"  \n:red[{'; '.join(data['errors'])}]"
    return "Research worker", detail


def _research_aggregate(data: dict) -> tuple[str, str]:
    lines = [f"- {cause['cause']}: **{cause['count']}**" for cause in data["root_causes"]]
    excluded = f"  \nexcluded as not relevant: {_ids(data['excluded'])}" if data.get("excluded") else ""
    return "Aggregator", f"coverage **{data['coverage']}**, {data['period']}{excluded}  \n" + "\n".join(lines)


def _retrieval(data: dict) -> tuple[str, str]:
    found = _ids(data["chunk_ids"]) or "nothing above the minimum score"
    return "Retrieval", f"found **{data['found']}** chunks: {found}"


def _tool_agent(data: dict) -> tuple[str, str]:
    tools = ", ".join(f"`{name}`" for name in data["tools"]) or "none"
    if not data["calls"]:
        return "Tool agent", f"tools for this role: {tools}  \nwriting the answer"
    calls = "  \n".join(f"calling `{call['name']}` {call['args']}" for call in data["calls"])
    return "Tool agent", f"tools for this role: {tools}  \n{calls}"


def _tool_executor(data: dict) -> tuple[str, str]:
    colours = {"ok": "green", "denied": "red", "unknown": "red"}
    lines = [f"`{r['tool']}`: :{colours.get(r['status'], 'orange')}[{r['status']}]" for r in data["results"]]
    return "Tool executor", "  \n".join(lines)


def _validator(data: dict) -> tuple[str, str]:
    if not data["ok"]:
        return "Validator", f":red[rejected] - {data['reason']}"
    return "Validator", f":green[passed] - cited {_ids(data['cited']) or 'no citations needed'}"


DESCRIBERS = {
    "supervisor": _supervisor,
    "retrieval": _retrieval,
    "research_plan": _research_plan,
    "research_execute": _research_execute,
    "research_worker": _research_worker,
    "research_aggregate": _research_aggregate,
    "tool_agent": _tool_agent,
    "tool_executor": _tool_executor,
    "response": lambda data: ("Response agent", f"draft written (attempt {data['attempt']})"),
    "validator": _validator,
}


def describe_node(data: dict) -> tuple[str, str]:
    describer = DESCRIBERS.get(data["node"])
    return describer(data) if describer else (data["node"], "")


def describe(event: str, data: dict) -> tuple[str, str] | None:
    if event == "start":
        return "Started", f"thread `{data['thread_id']}`"
    if event == "node_end":
        return describe_node(data)
    if event == "interrupt":
        actions = "  \n".join(f"`{a['tool']}` {a['args']}" for a in data["actions"])
        return "Paused for approval", f":orange[waiting for a human decision]  \n{actions}"
    if event == "done":
        return ("Waiting", "run is paused until someone approves or rejects") if data.get("awaiting_approval") \
            else ("Done", "answer delivered")
    if event == "error":
        return "Error", f":red[{data['message']}]"
    return None
