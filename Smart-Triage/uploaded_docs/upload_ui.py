import streamlit as st
import os
import pandas as pd

from core.loader import load_document
from core.chunker import chunk_text
from core.embedder import embed_texts
from core.vectordb import (
    init_db,
    load_db,
    add_embeddings,
    remove_document
)
from config.settings import RAW_DATA_PATH, CHUNK_SIZE, CHUNK_OVERLAP


def render_upload_ui():
    st.header("📥 Knowledge Base Ingestion")

    # =========================
    # USE CASE
    # =========================
    use_case = st.selectbox(
        "Select Use Case",
        ["AUTH", "INVENTORY", "PAYMENT", "QA", "GENERAL"]
    )

    # =========================
    # FILE UPLOAD
    # =========================
    files = st.file_uploader(
        "Upload documents",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True
    )

    # =========================
    # PROCESS & INDEX
    # =========================
    if st.button("Process & Index") and files:
        os.makedirs(RAW_DATA_PATH, exist_ok=True)

        for file in files:
            path = os.path.join(RAW_DATA_PATH, file.name)

            with open(path, "wb") as f:
                f.write(file.read())

            # 🔥 Remove old version if exists
            remove_document(file.name)

            text = load_document(path)
            chunks = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
            embeddings = embed_texts(chunks)

            index, metadata = load_db()
            if index is None:
                index, metadata = init_db(len(embeddings[0]))

            add_embeddings(
                index=index,
                metadata=metadata,
                embeddings=embeddings,
                chunks=chunks,
                filename=file.name,
                use_case=use_case
            )

        st.success("✅ Documents indexed successfully")

    # =========================
    # INDEXED FILE TABLE
    # =========================
    st.divider()
    st.subheader("📊 Indexed Files Overview")

    _, metadata = load_db()

    if metadata:
        file_map = {}

        for m in metadata:
            doc = m["document"]
            if doc not in file_map:
                file_map[doc] = {
                    "File Name": doc,
                    "Use Case": m["use_case"],
                    "Indexed At": m["timestamp"]
                }

        df = pd.DataFrame(file_map.values())

        col1, col2 = st.columns([1, 3])

        with col1:
            st.metric("📁 Total Indexed Files", len(df))

        with col2:
            st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No files indexed yet.")
