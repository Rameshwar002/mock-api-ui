# install required packages:
# pip install streamlit chromadb sentence-transformers python-docx pypdf ollama

import os
import chromadb
import docx
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
import streamlit as st
import ollama  # LLM for answering questions

# ========= CONFIG =========
UPLOAD_DIR = "uploaded_docs"
COLLECTION_NAME = "my_documents"
EMBED_MODEL = "all-MiniLM-L6-v2"
LLM_MODEL = "llama3.2"   # Ollama LLM
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
TOP_K = 3
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

# ---- Embedding ----
embedder = SentenceTransformer(EMBED_MODEL)

def get_embedding(text):
    return embedder.encode(text).tolist()

# ---- Setup ChromaDB ----
chroma_client = chromadb.Client()
collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)

# ---- Streamlit UI ----
st.title("📚 Document Search + LLM Answering")

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

        # Read text
        ext = os.path.splitext(file.name)[1].lower()
        if ext == ".pdf":
            raw_text = load_pdf(save_path)
        elif ext == ".txt":
            raw_text = load_txt(save_path)
        elif ext == ".docx":
            raw_text = load_docx(save_path)
        else:
            st.warning(f"⚠️ Unsupported file: {file.name}")
            continue

        chunks = chunk_text(raw_text)
        for i, chunk in enumerate(chunks):
            emb = get_embedding(chunk)
            collection.add(
                documents=[chunk],
                embeddings=[emb],
                metadatas=[{"filename": file.name, "chunk_id": i}],
                ids=[f"{file.name}_{i}"]
            )
        st.info(f"📄 Processed {file.name} → {len(chunks)} chunks")

st.markdown("---")

# ---- Query + LLM Section ----
query = st.text_input("🔍 Enter your question")

if query:
    # 1️⃣ Retrieve top-k chunks
    q_emb = get_embedding(query)
    results = collection.query(query_embeddings=[q_emb], n_results=TOP_K)
    retrieved_docs = results["documents"][0]
    retrieved_meta = results["metadatas"][0]

    context = "\n\n".join(retrieved_docs)

    # 2️⃣ Build prompt for LLM
    prompt = f"""You are a helpful assistant. 
Answer the question using only the following context:

{context}

Question: {query}
Answer:"""

    # 3️⃣ Ask Ollama LLM
    response = ollama.chat(model=LLM_MODEL, messages=[{"role": "user", "content": prompt}])
    answer = response["message"]["content"]

    # 4️⃣ Display
    st.subheader("💡 Answer from LLM")
    st.write(answer)

    st.subheader("📚 Sources (Top Chunks)")
    for doc, meta in zip(retrieved_docs, retrieved_meta):
        st.write(f"- {meta['filename']} (chunk {meta['chunk_id']}) → {doc[:300]}...")
