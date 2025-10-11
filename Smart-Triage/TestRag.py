import os
import chromadb
import docx
from sentence_transformers import SentenceTransformer
import streamlit as st
from PyPDF2 import PdfReader
# import ollama
import shutil

# ========= CONFIG =========
UPLOAD_DIR = "mock_docs"
COLLECTION_NAME = "connected_cars_docs"
EMBED_MODEL = "all-MiniLM-L6-v2"
LLM_MODEL = "llama3.2"
TOP_K = 2
# ==========================

st.set_page_config(page_title="Smart Flow RAG Test", layout="wide")


# ---- Utility Functions ----
def load_pdf(file_path):
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        if page.extract_text():
            text += page.extract_text() + "\n"
    return text

def load_txt(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def load_docx(file_path):
    doc = docx.Document(file_path)
    return "\n".join([p.text for p in doc.paragraphs])

def chunk_text(text, chunk_size=1000, overlap=100):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


# ---- Initialize Vector DB ----
chroma_client = chromadb.Client()
collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)
embedder = SentenceTransformer(EMBED_MODEL)


# ---- 📚 File Upload UI ----
st.title("📚 RAG Document Uploader")

uploaded_files = st.file_uploader(
    "Upload PDF, TXT, or DOCX files",
    type=["pdf", "txt", "docx"],
    accept_multiple_files=True
)

if uploaded_files:
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    for file in uploaded_files:
        save_path = os.path.join(UPLOAD_DIR, file.name)
        with open(save_path, "wb") as f:
            f.write(file.getbuffer())
        st.success(f"✅ Saved {file.name}")

        ext = os.path.splitext(file.name)[1].lower()
        if ext == ".pdf":
            text = load_pdf(save_path)
        elif ext == ".txt":
            text = load_txt(save_path)
        elif ext == ".docx":
            text = load_docx(save_path)
        else:
            st.warning(f"⚠️ Unsupported file: {file.name}")
            continue

        chunks = chunk_text(text)
        for i, chunk in enumerate(chunks):
            emb = embedder.encode(chunk).tolist()
            collection.add(
                documents=[chunk],
                embeddings=[emb],
                metadatas=[{"filename": file.name, "chunk_id": i}],
                ids=[f"{file.name}_{i}"]
            )
        st.info(f"📄 Processed {file.name} → {len(chunks)} chunks")

st.markdown("---")

# ---- JIRA Description Input ----
query = st.text_area(
    "🧾 Paste Ticket Description (from JIRA)",
    placeholder="e.g. Vehicle not charging even when charger is connected...",
)

if st.button("🔍 Analyze Issue"):
    if not query.strip():
        st.warning("Please enter a description first.")
    else:
        q_emb = embedder.encode(query).tolist()
        results = collection.query(query_embeddings=[q_emb], n_results=TOP_K)

        retrieved_docs = results["documents"][0]
        retrieved_meta = results["metadatas"][0]

        context = "\n\n".join(retrieved_docs)
        system_name = retrieved_meta[0]["filename"].replace("_Issues.docx", "").replace(".docx", "")

        st.subheader(f"🧩 Identified System: **{system_name}**")

        # ---- Prompt for LLM ----
        prompt = f"""
You are a diagnostic assistant for connected vehicles.
Analyze the issue description below and explain which vehicle system it belongs to and what possible actions to take.

Description:
{query}

Relevant Knowledge:
{context}

Give a structured answer:
1. System Name
2. Root Cause (based on context)
3. Recommended Actions
        """

        # try:
        #     response = ollama.chat(model=LLM_MODEL, messages=[{"role": "user", "content": prompt}])
        #     st.subheader("🤖 LLM Analysis")
        #     st.markdown(response["message"]["content"])
        # except Exception as e:
        #     st.error(f"LLM Error: {e}")

        # ---- Show Retrieved Context ----
        st.markdown("---")
        st.subheader("📚 Retrieved Context")
        for doc, meta in zip(retrieved_docs, retrieved_meta):
            st.write(f"**From:** {meta['filename']} (chunk {meta.get('chunk_id')})")
            st.text(doc[:500] + "...")
