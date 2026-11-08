import ast

from langsmith import traceable

from app.knowledge.catalog import CatalogView, Row, months_ago

MAX_BATCHES = 8
MAX_BATCH_SIZE = 6

ALLOWED_NODES = (
    ast.Module, ast.Assign, ast.Name, ast.Load, ast.Store, ast.Call, ast.keyword,
    ast.Constant, ast.Attribute, ast.BinOp, ast.Add,
)
ALLOWED_FUNCTIONS = {"batch", "months_ago", "unique"}
ALLOWED_CATALOG_METHODS = {"filter", "search"}

PLAN_LANGUAGE = """\
rows = catalog.filter(document_type=..., department=..., service=..., tag=..., since=...)  # all optional
rows = catalog.search("word", since=...)  # title or tag contains the word; since optional
rows = unique(rows_a + rows_b)         # combine two results
since = months_ago(12)                 # date 12 months ago, like "2025-11-07"
batches = batch(rows, size=4)          # REQUIRED last line: split doc ids into groups"""


class PlanRejected(Exception):
    pass


def unique(rows: list[Row]) -> list[Row]:
    seen: dict[str, Row] = {}
    for row in rows:
        seen.setdefault(row.doc_id, row)
    return list(seen.values())


def batch(rows: list[Row], size: int = 4) -> list[list[str]]:
    size = max(1, min(int(size), MAX_BATCH_SIZE))
    ids = [row.doc_id for row in sorted(rows, key=lambda row: row.date)]
    return [ids[start:start + size] for start in range(0, len(ids), size)]


def check_plan(code: str) -> ast.Module:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise PlanRejected(f"not valid Python: {exc.msg}") from None

    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_NODES):
            raise PlanRejected(f"{type(node).__name__} is not allowed")
        if isinstance(node, ast.Name) and node.id.startswith("_"):
            raise PlanRejected(f"name '{node.id}' is not allowed")
        if isinstance(node, ast.Attribute):
            on_catalog = isinstance(node.value, ast.Name) and node.value.id == "catalog"
            if not on_catalog or node.attr not in ALLOWED_CATALOG_METHODS or isinstance(node.ctx, ast.Store):
                raise PlanRejected(f"attribute '.{node.attr}' is not allowed")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id not in ALLOWED_FUNCTIONS:
            raise PlanRejected(f"function '{node.func.id}' is not allowed")
    return tree


@traceable(run_type="tool", name="sandbox_run_plan", process_inputs=lambda inputs: {"code": inputs["code"]})
def run_plan(code: str, view: CatalogView) -> list[list[str]]:
    tree = check_plan(code)
    namespace = {"catalog": view, "batch": batch, "months_ago": months_ago, "unique": unique}
    try:
        exec(compile(tree, "<plan>", "exec"), {"__builtins__": {}}, namespace)  # noqa: S102 - allow-listed plan
    except Exception as exc:  # noqa: BLE001 - any failure means the plan is rejected
        raise PlanRejected(f"plan failed: {type(exc).__name__}: {exc}") from None

    batches = namespace.get("batches")
    check_batches(batches, view.ids())
    return batches


def check_batches(batches, known_ids: set[str]) -> None:
    if not isinstance(batches, list) or not batches:
        raise PlanRejected("the plan must end with a non-empty 'batches' list")
    if len(batches) > MAX_BATCHES:
        raise PlanRejected(f"too many batches ({len(batches)} > {MAX_BATCHES})")
    for group in batches:
        if not isinstance(group, list) or not group or len(group) > MAX_BATCH_SIZE:
            raise PlanRejected("each batch must be a list of 1 to 6 document ids")
        if any(doc_id not in known_ids for doc_id in group):
            raise PlanRejected("batches may only contain documents from the catalog")
