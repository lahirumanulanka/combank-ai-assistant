def _ids(chunk_ids: list[str]) -> str:
    return ", ".join(f"`{chunk_id}`" for chunk_id in chunk_ids)


def describe_node(data: dict) -> tuple[str, str]:
    node = data["node"]
    if node == "supervisor":
        return "Supervisor", f"route **{data['route']}** - {data['rationale']}  \nsearch: _{data['search_query']}_"
    if node == "retrieval":
        found = _ids(data["chunk_ids"]) or "nothing above the minimum score"
        return "Retrieval", f"found **{data['found']}** chunks: {found}"
    if node == "response":
        return "Response agent", f"draft written (attempt {data['attempt']})"
    if node == "validator":
        if not data["ok"]:
            return "Validator", f":red[rejected] - {data['reason']}"
        cited = _ids(data["cited"]) or "no citations needed"
        return "Validator", f":green[passed] - cited {cited}"
    return node, ""


def describe(event: str, data: dict) -> tuple[str, str] | None:
    if event == "start":
        return "Started", f"thread `{data['thread_id']}`"
    if event == "node_end":
        return describe_node(data)
    if event == "done":
        return "Done", "answer delivered"
    if event == "error":
        return "Error", f":red[{data['message']}]"
    return None
