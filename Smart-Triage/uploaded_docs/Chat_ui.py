import streamlit as st
from core.retriever import retrieve
from core.vectordb import get_indexed_file_count


def format_answer(text: str) -> str:
    """
    Convert chunk text into readable markdown
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return ""

    heading = lines[0]
    body = lines[1:]

    md = f"**{heading}**\n\n"
    for line in body:
        md += f"- {line}\n"

    return md


def render_chat_ui():
    col1, col2 = st.columns([3, 1])

    # RIGHT SIDE – Stats
    with col2:
        st.markdown("### 📊 Knowledge Stats")
        st.metric(
            label="📁 Indexed Files",
            value=get_indexed_file_count()
        )

        selected_use_case = st.selectbox(
            "🎯 Filter by Use Case",
            options=["All", "API spec", "Puml"]
        )

    # LEFT SIDE – Chat
    with col1:
        st.header("💬 Knowledge Chat (RAG Retrieval Only)")

        query = st.text_input("Ask your question")

        if st.button("Search") and query:
            use_case = None if selected_use_case == "All" else selected_use_case

            results = retrieve(query, use_case=use_case)

            if not results:
                st.warning("No relevant information found")
                return

            for i, r in enumerate(results, 1):
                st.markdown(f"### 🔎 Result {i}")
                st.caption(
                    f"📄 {r['document']} | 🧩 {r['use_case']} | 🔢 Score: {r['score']:.4f}"
                )

                st.markdown(format_answer(r["text"]))
                st.markdown("---")
