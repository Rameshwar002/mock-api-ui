import streamlit as st
from ui.upload_ui import render_upload_ui
from ui.chat_ui import render_chat_ui

st.set_page_config(layout="wide")

st.sidebar.title("RAG Knowledge System")
page = st.sidebar.radio(
    "Navigation",
    ["📥 Upload Knowledge", "💬 Chat"]
)

if page == "📥 Upload Knowledge":
    render_upload_ui()
else:
    render_chat_ui()
