from datetime import date

from app.core.rbac import Role, allowed_access_levels
from app.knowledge.bm25 import SparseVector
from app.knowledge.chunking import date_as_number


def scale_for_hybrid(dense: list[float], sparse: SparseVector, alpha: float) -> tuple[list[float], SparseVector]:
    if not 0 <= alpha <= 1:
        raise ValueError("alpha must be between 0 and 1")

    scaled_dense = [value * alpha for value in dense]
    scaled_sparse: SparseVector = {
        "indices": sparse["indices"],
        "values": [value * (1 - alpha) for value in sparse["values"]],
    }
    return scaled_dense, scaled_sparse


def build_filter(role: Role, document_type: str | None = None, since: date | None = None) -> dict:
    metadata_filter: dict = {"access_level": {"$in": allowed_access_levels(role)}}
    if document_type:
        metadata_filter["document_type"] = {"$eq": document_type}
    if since:
        metadata_filter["created_on"] = {"$gte": date_as_number(since)}
    return metadata_filter
