import time

import streamlit as st
from api_client import ApiClient, ApiError
from panel import describe

st.set_page_config(page_title="Commercial Bank Knowledge Assistant", layout="wide")
client = ApiClient()


def start_new_chat() -> None:
    st.session_state.thread_id = None
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


def run_turn(prompt: str, chat_col, box) -> None:
    with chat_col:
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            text, answer, sources = "", "", []
            started = time.time()
            try:
                for event, data in client.stream_chat(st.session_state.token, prompt, st.session_state.thread_id):
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
                    elif event == "done":
                        answer = data["answer"]
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

            placeholder.markdown(answer or text)
            show_sources(sources)

    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.messages.append({"role": "assistant", "content": answer or text, "sources": sources})


def chat_screen() -> None:
    sidebar()
    prompt = st.chat_input("Ask about policies, incidents, runbooks, specs...")
    if prompt:
        st.session_state.activity = []

    chat_col, panel_col = st.columns([3, 2])

    with panel_col:
        st.subheader("Agent activity")
        box = st.container(border=True, height=560)
        for item in st.session_state.activity:
            show_step(box, *item)

    with chat_col:
        st.subheader("Chat")
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                show_sources(message.get("sources", []))

    if prompt:
        run_turn(prompt, chat_col, box)


if "token" in st.session_state:
    chat_screen()
else:
    login_screen()
