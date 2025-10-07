# vector_query.py
from chromadb import PersistentClient
from sentence_transformers import SentenceTransformer

DB_DIR = "chroma_data"
COLLECTION_NAME = "my_documents"

embed_model = SentenceTransformer("all-MiniLM-L6-v2")
client = PersistentClient(path=DB_DIR)
collection = client.get_collection(COLLECTION_NAME)

def query_vector_db(query_text, top_k=2):
    if not query_text:
        return {"error": "No query text provided"}

    try:
        query_emb = embed_model.encode([query_text]).tolist()
        results = collection.query(query_embeddings=query_emb, n_results=top_k)

        docs = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]

        output = [
            {"document": doc, "score": round(1 - dist, 2)}
            for doc, dist in zip(docs, distances)
        ]
        return {"matches": output}
    except Exception as e:
        return {"error": str(e)}
