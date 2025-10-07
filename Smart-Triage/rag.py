# rag_ui.py
# Run using: streamlit run rag_ui.py

import os
import streamlit as st
import chromadb
from sentence_transformers import SentenceTransformer
import docx
from PyPDF2 import PdfReader

# ========= CONFIG =========
UPLOAD_DIR = "uploaded_docs"
DB_DIR = "chroma_data"   # persistent directory for Chroma
COLLECTION_NAME = "my_documents"
EMBED_MODEL = "all-MiniLM-L6-v2"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
# ==========================

# ---- Loaders ----
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

# ---- Chunking ----
def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    tokens = text.split()
    chunks = []
    for i in range(0, len(tokens), chunk_size - overlap):
        chunk = " ".join(tokens[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks

# ---- Setup Embedding + DB ----
embedder = SentenceTransformer(EMBED_MODEL)
client = chromadb.PersistentClient(path=DB_DIR)
collection = client.get_or_create_collection(name=COLLECTION_NAME)

# ---- Streamlit UI ----
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
st.success("✅ Documents added successfully! Now you can close this and run the main UI.")
