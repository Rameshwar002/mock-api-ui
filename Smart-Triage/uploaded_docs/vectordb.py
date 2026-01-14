import os
import faiss
import pickle
import numpy as np
from datetime import datetime
from config.settings import VECTOR_DB_PATH

INDEX_PATH = f"{VECTOR_DB_PATH}/index.faiss"
META_PATH = f"{VECTOR_DB_PATH}/metadata.pkl"


def init_db(dim):
    index = faiss.IndexFlatL2(dim)
    return index, []


def save_db(index, metadata):
    os.makedirs(VECTOR_DB_PATH, exist_ok=True)
    faiss.write_index(index, INDEX_PATH)
    with open(META_PATH, "wb") as f:
        pickle.dump(metadata, f)


def load_db():
    if not os.path.exists(INDEX_PATH) or not os.path.exists(META_PATH):
        return None, []
    index = faiss.read_index(INDEX_PATH)
    with open(META_PATH, "rb") as f:
        metadata = pickle.load(f)
    return index, metadata


# 🔥 REMOVE OLD VERSION OF FILE (SAFE FAISS REBUILD)
def remove_document(filename):
    index, metadata = load_db()
    if index is None or not metadata:
        return

    # Keep chunks of other documents only
    remaining = [m for m in metadata if m["document"] != filename]

    # If nothing left → reset DB
    if not remaining:
        if os.path.exists(INDEX_PATH):
            os.remove(INDEX_PATH)
        if os.path.exists(META_PATH):
            os.remove(META_PATH)
        return

    # Rebuild FAISS
    from core.embedder import embed_texts

    texts = [m["text"] for m in remaining]
    embeddings = embed_texts(texts)

    dim = len(embeddings[0])
    new_index = faiss.IndexFlatL2(dim)
    new_index.add(np.array(embeddings).astype("float32"))

    save_db(new_index, remaining)


def add_embeddings(index, metadata, embeddings, chunks, filename, use_case):
    index.add(np.array(embeddings).astype("float32"))

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for chunk in chunks:
        metadata.append({
            "text": chunk,
            "document": filename,
            "use_case": use_case,
            "timestamp": timestamp
        })

    save_db(index, metadata)


def get_indexed_file_count():
    _, metadata = load_db()
    if not metadata:
        return 0
    return len(set(m["document"] for m in metadata))
