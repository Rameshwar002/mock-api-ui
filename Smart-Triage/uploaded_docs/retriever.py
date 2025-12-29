import numpy as np
from core.embedder import embed_texts
from core.vectordb import load_db
from config.settings import TOP_K

def retrieve(query):
    index, metadata = load_db()
    if index is None:
        return []

    query_vec = embed_texts([query])
    distances, indices = index.search(
        np.array(query_vec).astype("float32"),
        TOP_K * 3
    )

    results = []
    for idx in indices[0]:
        if idx < len(metadata):
            results.append(metadata[idx])

    return results[:TOP_K]
