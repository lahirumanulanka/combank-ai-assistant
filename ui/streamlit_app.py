import time

import streamlit as st
from api_client import ApiClient, ApiError
from panel import describe

st.set_page_config(page_title="Commercial Bank Knowledge Assistant", layout="wide")
client = ApiClient()


def start_new_chat() -> None:
    st.session_state.rated = set()
    st.session_state.thread_id = None
    st.session_state.pending = None
    st.session_state.messages = []
    st.session_state.activity = []


def login_screen() -> None:
    st.title("Commercial Bank Knowledge Assistant")
    st.caption("Internal assistant for policies, incidents, runbooks and specs.")

    with st.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")

    if submitted:
        try:
            session = client.login(username, password)
        except ApiError as exc:
            st.error(exc.message)
            return
        st.session_state.token = session["access_token"]
        st.session_state.name = session["name"]
        st.session_state.role = session["role"]
        start_new_chat()
        st.rerun()


def sidebar() -> None:
    with st.sidebar:
        st.subheader(st.session_state.name)
        st.caption(f"Role: **{st.session_state.role}**")
        if st.button("New chat", use_container_width=True):
            start_new_chat()
            st.rerun()
        if st.button("Sign out", use_container_width=True):
            st.session_state.clear()
            st.rerun()


def show_step(box, seconds: float, title: str, detail: str) -> None:
    box.markdown(f"**{title}** · {seconds:.1f}s  \n{detail}")


def show_sources(sources: list[str]) -> None:
    if sources:
        st.caption("Sources: " + ", ".join(f"`{source}`" for source in sources))


def stream_answer(events, chat_col, box, user_text: str | None = None) -> None:
    with chat_col:
        if user_text:
            with st.chat_message("user"):
                st.markdown(user_text)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            text, answer, sources, pending, run_id = "", "", [], None, None
            started = time.time()
            try:
                for event, data in events:
                    if event == "token":
                        text += data["text"]
                        placeholder.markdown(text + "▌")
                        continue
                    if event == "start":
                        st.session_state.thread_id = data["thread_id"]
                    elif event == "node_end" and data["node"] == "validator":
                        sources = data["cited"]
                        if not data["ok"]:
                            text = ""
                    elif event == "interrupt":
                        pending = data
                    elif event == "done":
                        answer = data["answer"]
                        run_id = data.get("run_id")
                    elif event == "error":
                        answer = data["message"]

                    step = describe(event, data)
                    if step:
                        item = (time.time() - started, *step)
                        st.session_state.activity.append(item)
                        show_step(box, *item)
            except ApiError as exc:
                answer = exc.message
                if exc.status == 401:
                    answer += " Please sign out and sign in again."

            if pending:
                answer = "This needs a human decision before it runs. Please approve or reject it below."
            placeholder.markdown(answer or text)
            show_sources(sources)

    if user_text:
        st.session_state.messages.append({"role": "user", "content": user_text})
    st.session_state.messages.append(
        {"role": "assistant", "content": answer or text, "sources": sources, "run_id": run_id}
    )
    if pending:
        st.session_state.pending = pending
        st.rerun()


def feedback_buttons(run_id: str) -> None:
    rating = st.feedback("thumbs", key=f"feedback-{run_id}")
    if rating is None or run_id in st.session_state.rated:
        return
    try:
        result = client.send_feedback(st.session_state.token, run_id, rating)
    except ApiError as exc:
        st.toast(exc.message)
        return
    st.session_state.rated.add(run_id)
    st.toast("Thanks! Feedback sent to LangSmith." if result["sent_to_langsmith"] else "Thanks! Feedback recorded.")


def approval_box(pending: dict) -> bool | None:
    with st.container(border=True):
        st.warning(pending["question"])
        for action in pending["actions"]:
            st.code(f"{action['tool']}({action['args']})")
        approve_col, reject_col = st.columns(2)
        if approve_col.button("Approve", type="primary", use_container_width=True):
            return True
        if reject_col.button("Reject", use_container_width=True):
            return False
    return None


def chat_screen() -> None:
    sidebar()
    pending = st.session_state.get("pending")
    prompt = st.chat_input("Ask about policies, incidents, runbooks, specs...", disabled=bool(pending))
    if prompt:
        st.session_state.activity = []

    chat_col, panel_col = st.columns([3, 2])

    with panel_col:
        st.subheader("Agent activity")
        box = st.container(border=True, height=560)
        for item in st.session_state.activity:
            show_step(box, *item)

    decision = None
    with chat_col:
        st.subheader("Chat")
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                show_sources(message.get("sources", []))
                if message.get("run_id"):
                    feedback_buttons(message["run_id"])
        if pending:
            decision = approval_box(pending)

    if prompt:
        stream_answer(client.stream_chat(st.session_state.token, prompt, st.session_state.thread_id),
                      chat_col, box, user_text=prompt)
    elif decision is not None:
        st.session_state.pending = None
        events = client.resume_chat(st.session_state.token, st.session_state.thread_id, decision)
        stream_answer(events, chat_col, box, user_text="Approved." if decision else "Rejected.")
        st.rerun()


if "token" in st.session_state:
    chat_screen()
else:
    login_screen()
