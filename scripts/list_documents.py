from collections import Counter
from pathlib import Path

from app.core.rbac import Role
from app.knowledge.documents import load_documents, visible_to


def main() -> None:
    documents = load_documents(Path("data/docs"))

    print(f"{'DOC ID':<22} {'TYPE':<14} {'DEPARTMENT':<11} {'ACCESS':<13} DATE")
    for doc in documents:
        m = doc.meta
        print(f"{m.doc_id:<22} {m.document_type:<14} {m.department:<11} {m.access_level:<13} {m.created_date}")

    print(f"\nTotal: {len(documents)}")
    print("By type:", dict(Counter(doc.meta.document_type for doc in documents)))
    for role in Role:
        print(f"{role.value:<8} can see {len(visible_to(documents, role))}")


if __name__ == "__main__":
    main()
