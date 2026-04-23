import json
import faiss
from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
INDEX_FILE = "data/faiss.index"
METADATA_FILE = "data/metadata.jsonl"
TOP_K = 5


def load_metadata(path: str) -> list[dict]:
    metadata = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                metadata.append(json.loads(line))
    return metadata


def search(query: str, index, metadata: list[dict], model, k: int = TOP_K):
    query_vector = model.encode(
        [query],
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).astype("float32")

    scores, positions = index.search(query_vector, k)

    results = []
    for score, pos in zip(scores[0], positions[0]):
        if pos == -1:
            continue
        article = metadata[pos]
        results.append({
            "score":          float(score),
            "law_title":      article["law_title"],
            "article_number": article["article_number"],
            "text":           article["text"],
        })
    return results


def main():
    print("Loading model and index...")
    model = SentenceTransformer(MODEL_NAME)
    index = faiss.read_index(INDEX_FILE)
    metadata = load_metadata(METADATA_FILE)
    print(f"Index has {index.ntotal} articles.\n")

    while True:
        try:
            query = input("Intrebare (sau 'exit'): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nLa revedere!")
            break

        if query.lower() == "exit":
            break
        if not query:
            continue

        results = search(query, index, metadata, model)

        print(f"\nTop {TOP_K} rezultate pentru: '{query}'\n")
        for i, r in enumerate(results, 1):
            print(f"[{i}] scor={r['score']:.3f} | {r['law_title']} | {r['article_number']}")
            print(f"    {r['text'][:200]}")
            print()


if __name__ == "__main__":
    main()
