import os
import json
import faiss
from sentence_transformers import SentenceTransformer
from groq import Groq

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(BASE_DIR, "scraper/data/faiss.index")
METADATA_FILE = os.path.join(BASE_DIR, "scraper/data/metadata.jsonl")
TOP_K = 5
GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """
Ești RoCodex, un asistent juridic specializat în legislația română.
Răspunzi la întrebări despre legi românești bazându-te EXCLUSIV pe articolele de lege furnizate în context.
Reguli stricte:
1. Răspunde numai pe baza articolelor furnizate. Nu inventa informații.
2. Citează întotdeauna sursa: legea și numărul articolului.
3. Dacă articolele furnizate nu conțin răspunsul, spune clar: "Nu am găsit informații relevante în baza de date pentru această întrebare."
4. Răspunde în română, clar și structurat.
5. Nu oferi sfaturi juridice personalizate. Indică utilizatorul să consulte un avocat pentru situații specifice.
"""

_model = None
_index = None
_metadata = None

def _load_resources():
    """
    Load the embedding model, FAISS index, and metadata into memory.
    """
    global _model, _index, _metadata

    if _model is None:
        print("Loading embedding model...")
        _model = SentenceTransformer(MODEL_NAME)

    if _index is None:
        print("Loading FAISS index...")
        _index = faiss.read_index(INDEX_FILE)

    if _metadata is None:
        print("Loading metadata...")
        _metadata = []
        with open(METADATA_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    _metadata.append(json.loads(line))

    return _model, _index, _metadata


def retrieve(query: str, k: int = TOP_K) -> list[dict]:
    """
    Find the k most semantically similar articles to the query.
    Returns a list of dicts, each containing:
      - law_title: e.g. "CODUL MUNCII 24/01/2003"
      - article_number: e.g. "Articolul 145"
      - text: the article's cleaned text
      - score: cosine similarity score (0-1, higher = more relevant)
    """
    model, index, metadata = _load_resources()

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
            "law_title":      article["law_title"],
            "article_number": article["article_number"],
            "text":           article["text"],
            "score":          float(score),
        })

    return results


def build_prompt(query: str, articles: list[dict]) -> str:
    """
    Build the user message that combines the retrieved articles with the question.
    """
    context_parts = []
    for i, article in enumerate(articles, 1):
        context_parts.append(
            f"[Sursa {i}] {article['law_title']} — {article['article_number']}\n"
            f"{article['text']}"
        )

    context = "\n\n---\n\n".join(context_parts)

    return f"""Pe baza următoarelor articole din legislația română, răspunde la întrebarea de mai jos.
ARTICOLE RELEVANTE:
{context}
ÎNTREBARE:
{query}
Răspuns (citează sursele folosind [Sursa N]):"""

def answer(query: str, groq_api_key: str) -> dict:
    """
    Parameters:
      query        — the user's question in Romanian
      groq_api_key — the Groq API key the user has to provide
    Returns a dict:
      {
        "answer":   "Răspunsul generat de LLM...",
        "sources":  [list of retrieved articles with scores],
        "query":    "întrebarea originală"
      }
    """
    articles = retrieve(query, k=TOP_K)

    if not articles:
        return {
            "answer":  "Nu am putut găsi articole relevante în baza de date.",
            "sources": [],
            "query":   query,
        }

    prompt = build_prompt(query, articles)

    client = Groq(api_key=groq_api_key)

    chat_completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        temperature=0.1,
        max_tokens=1024,
    )

    generated_answer = chat_completion.choices[0].message.content

    return {
        "answer":  generated_answer,
        "sources": articles,
        "query":   query,
    }


if __name__ == "__main__":
    api_key = os.environ.get("GROQ_API_KEY") or (
        input("Introdu Groq API key: ").strip()
    )

    print("\nRoCodex RAG — test CLI")
    print("Scrie 'exit' pentru a ieși.\n")

    while True:
        try:
            query = input("Întrebare: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if query.lower() == "exit":
            break
        if not query:
            continue

        print("\nCaut articole relevante și generez răspuns...\n")
        result = answer(query, api_key)

        print("=" * 60)
        print(result["answer"])
        print("\nSURSE FOLOSITE:")
        for i, src in enumerate(result["sources"], 1):
            print(f"  [{i}] scor={src['score']:.3f} | {src['law_title']} | {src['article_number']}")
        print("=" * 60)
        print()
