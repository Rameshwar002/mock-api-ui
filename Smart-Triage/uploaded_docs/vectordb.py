import os
import faiss
import pickle
import numpy as np
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
        
def get_indexed_file_count():
    _, metadata = load_db()
    if not metadata:
        return 0
    return len(set(m["document"] for m in metadata))

def load_db():
    if not os.path.exists(INDEX_PATH):
        return None, []
    index = faiss.read_index(INDEX_PATH)
    with open(META_PATH, "rb") as f:
        metadata = pickle.load(f)
    return index, metadata

def add_embeddings(index, metadata, embeddings, chunks, filename, use_case):
    index.add(np.array(embeddings).astype("float32"))
    for chunk in chunks:
        metadata.append({
            "text": chunk,
            "document": filename,
            "use_case": use_case
        })
    save_db(index, metadata)
