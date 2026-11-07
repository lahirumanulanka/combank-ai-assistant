import argparse
import asyncio
from datetime import date

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.rbac import Role
from app.services.search import get_hybrid_search


async def main() -> None:
    parser = argparse.ArgumentParser(description="Try one hybrid search from the terminal.")
    parser.add_argument("query")
    parser.add_argument("--role", default="viewer", choices=[role.value for role in Role])
    parser.add_argument("--alpha", type=float, default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--type", dest="document_type", default=None)
    parser.add_argument("--since", type=date.fromisoformat, default=None)
    args = parser.parse_args()

    settings = get_settings()
    configure_logging("WARNING", settings.log_json)

    results = await get_hybrid_search().search(
        args.query,
        Role(args.role),
        top_k=args.top_k,
        alpha=args.alpha,
        document_type=args.document_type,
        since=args.since,
    )

    print(f'"{args.query}"  role={args.role}  alpha={args.alpha or settings.hybrid_alpha}')
    if not results:
        print("  no results")
    for result in results:
        print(f"  {result.score:6.3f}  {result.chunk_id:<22} {result.access_level:<12} {result.section}")


if __name__ == "__main__":
    asyncio.run(main())
