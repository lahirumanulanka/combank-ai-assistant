import argparse
import asyncio
import uuid

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.core.config import MissingSetting, get_settings
from app.core.logging import configure_logging
from app.core.rbac import Role
from app.core.users import get_user
from app.graph.builder import build_default_graph
from app.graph.context import RuntimeContext


async def main() -> None:
    parser = argparse.ArgumentParser(description="Chat with the agents. Follow-up questions remember the chat.")
    parser.add_argument("--role", default="viewer", choices=[role.value for role in Role])
    args = parser.parse_args()

    settings = get_settings()
    configure_logging("WARNING", settings.log_json)

    user = get_user(args.role)
    context = RuntimeContext(user_id=user.username, role=user.role, name=user.name)
    graph = await build_default_graph(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": f"{user.username}-{uuid.uuid4().hex[:8]}"}}

    print(f"Chatting as {user.name} ({args.role}). Type 'exit' to stop.\n")
    while True:
        question = input("you> ").strip()
        if question.lower() in {"exit", "quit"}:
            break
        if not question:
            continue

        result = await graph.ainvoke({"messages": [HumanMessage(question)]}, config=config, context=context)
        cited = result.get("validation", {}).get("cited", [])
        print(f"  [route={result['route']} searched='{result['search_query']}' "
              f"attempts={result['attempts']} cited={cited}]")
        print(f"bot> {result['messages'][-1].content}\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except MissingSetting as exc:
        raise SystemExit(f"Setup problem: {exc}") from None
    except (KeyboardInterrupt, EOFError):
        print()
