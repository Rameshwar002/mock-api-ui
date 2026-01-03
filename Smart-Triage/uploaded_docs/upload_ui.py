import streamlit as st
import os
from core.loader import load_document
from core.chunker import chunk_text
from core.embedder import embed_texts
from core.vectordb import init_db, load_db, add_embeddings
from config.settings import RAW_DATA_PATH, CHUNK_SIZE, CHUNK_OVERLAP

def render_upload_ui():
    st.header("📥 Knowledge Base Ingestion")

    use_case = st.selectbox(
        "Select Use Case",
        ["AUTH", "INVENTORY", "PAYMENT", "QA", "GENERAL"]
    )

    files = st.file_uploader(
        "Upload documents",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True
    )

    if st.button("Process & Index") and files:
        os.makedirs(RAW_DATA_PATH, exist_ok=True)

        for file in files:
            path = os.path.join(RAW_DATA_PATH, file.name)
            with open(path, "wb") as f:
                f.write(file.read())

            text = load_document(path)
            chunks = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
            embeddings = embed_texts(chunks)

            index, metadata = load_db()
            if index is None:
                index, metadata = init_db(len(embeddings[0]))

            add_embeddings(
                index,
                metadata,
                embeddings,
                chunks,
                file.name,
                use_case
            )

        st.success("✅ Documents indexed successfully")
