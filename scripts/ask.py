import argparse
import asyncio

from langchain_core.messages import HumanMessage

from app.core.config import MissingSetting, get_settings
from app.core.logging import configure_logging
from app.core.rbac import Role
from app.core.users import get_user
from app.graph.builder import build_default_graph
from app.graph.context import RuntimeContext


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the agents one question from the terminal.")
    parser.add_argument("question")
    parser.add_argument("--role", default="viewer", choices=[role.value for role in Role])
    args = parser.parse_args()

    settings = get_settings()
    configure_logging("WARNING", settings.log_json)

    user = get_user(args.role)
    context = RuntimeContext(user_id=user.username, role=user.role, name=user.name)
    graph = build_default_graph()

    result = await graph.ainvoke({"messages": [HumanMessage(args.question)]}, context=context)

    print(f"role:      {args.role}  (model: {settings.llm_strong})")
    print(f"route:     {result['route']}  - {result['rationale']}")
    print(f"searched:  {result['search_query']}")
    print(f"passages:  {[chunk['chunk_id'] for chunk in result.get('retrieved', [])]}")
    print(f"\n{result['messages'][-1].content}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except MissingSetting as exc:
        raise SystemExit(f"Setup problem: {exc}") from None
