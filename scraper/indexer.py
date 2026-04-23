import json
import faiss
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
ARTICLES_FILE = Path("data/articles.jsonl")
INDEX_FILE = Path("data/faiss.index")
METADATA_FILE = Path("data/metadata.jsonl")
BATCH_SIZE = 32


def load_articles(path: Path) -> list[dict]:
    articles = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                articles.append(json.loads(line))
    print(f"Loaded {len(articles)} articles from {path}")
    return articles


def embed_articles(articles: list[dict], model: SentenceTransformer) -> np.ndarray:
    """
    Convert each article's 'chunk' field into a vector.
    Returns a 2D numpy array of shape (n_articles, embedding_dim).
    """
    chunks = [a["chunk"] for a in articles]
    all_embeddings = []

    print(f"Embedding {len(chunks)} articles in batches of {BATCH_SIZE}...")
    for i in tqdm(range(0, len(chunks), BATCH_SIZE)):
        batch = chunks[i : i + BATCH_SIZE]
        embeddings = model.encode(
            batch,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        all_embeddings.append(embeddings)

    return np.vstack(all_embeddings).astype("float32")


def build_index(embeddings: np.ndarray) -> faiss.Index:
    """
    Build a FAISS index from the embeddings.
    """
    dim = embeddings.shape[1]
    print(f"Building FAISS index — {len(embeddings)} vectors, dim={dim}")

    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    print(f"Index contains {index.ntotal} vectors")
    return index


def save_metadata(articles: list[dict], path: Path):
    """
    Save article metadata in the same order as the FAISS index.
    """
    with open(path, "w", encoding="utf-8") as f:
        for article in articles:
            meta = {
                "law_id":         article.get("law_id"),
                "law_title":      article.get("law_title"),
                "article_number": article.get("article_number"),
                "text":           article.get("text"),
                "chunk":          article.get("chunk"),
            }
            f.write(json.dumps(meta, ensure_ascii=False) + "\n")
    print(f"Saved metadata to {path}")


def main():
    # 1. Load articles
    articles = load_articles(ARTICLES_FILE)
    if not articles:
        print("No articles found. Run pipeline.py first.")
        return

    # 2. Load embedding model
    print(f"Loading model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    # 3. Embed all articles
    embeddings = embed_articles(articles, model)

    # 4. Build FAISS index
    index = build_index(embeddings)

    # 5. Save index and metadata
    faiss.write_index(index, str(INDEX_FILE))
    print(f"Saved FAISS index to {INDEX_FILE}")

    save_metadata(articles, METADATA_FILE)

    print("\nDone! Run retriever.py to search the index.")
    print(f"  Index:    {INDEX_FILE} ({INDEX_FILE.stat().st_size // 1024} KB)")
    print(f"  Metadata: {METADATA_FILE} ({METADATA_FILE.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
