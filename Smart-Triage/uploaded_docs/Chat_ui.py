import streamlit as st
from core.retriever import retrieve

def render_chat_ui():
    st.header("💬 Knowledge Chat (RAG Retrieval Only)")

    query = st.text_input("Ask your question")

    if st.button("Search") and query:
        results = retrieve(query)

        if not results:
            st.warning("No relevant information found")
            return

        for i, r in enumerate(results, 1):
            st.markdown(f"""
### Result {i}
**Document:** {r['document']}  
**Use Case:** {r['use_case']}

{r['text']}
---
""")
