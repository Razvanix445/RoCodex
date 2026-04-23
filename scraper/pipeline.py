import json
import time
import random
import argparse
import sys
import io
from pathlib import Path
from tqdm import tqdm

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from html_scraper import scrape_law
from cleaner import clean_law

DATA_DIR = Path("data")
LAWS_FILE = DATA_DIR / "laws.jsonl"
ARTICLES_FILE = DATA_DIR / "articles.jsonl"
FAILED_FILE = DATA_DIR / "failed_ids.txt"

IMPORTANT_LAW_IDS = {
     41627: "Codul Muncii - Legea 53/2003",
    175630: "Codul Civil - Legea 287/2009",
    109855: "Codul Penal - Legea 286/2009",
    140271: "Codul de Procedura Civila - Legea 134/2010",
    120609: "Codul de Procedura Penala - Legea 135/2010",
     38533: "Legea Societatilor Comerciale - Legea 31/1990",
}

def ensure_data_dir():
    """Create the data/ directory if it doesn't already exist."""
    DATA_DIR.mkdir(exist_ok=True)


def load_already_scraped() -> set[int]:
    """
    Read laws.jsonl and return the set of IDs we've already scraped.
    """
    if not LAWS_FILE.exists():
        return set()

    scraped = set()
    with open(LAWS_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                scraped.add(int(obj["id"]))
            except (json.JSONDecodeError, KeyError, ValueError):
                pass

    return scraped


def append_jsonl(filepath: Path, obj: dict):
    """
    Write one Python dict as a JSON line at the end of a file.
    """
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def polite_sleep(base_delay: float):
    """
    Wait for a randomized amount of time between requests.
    """
    jitter = random.uniform(-base_delay * 0.5, base_delay * 0.5)
    actual = max(1.0, base_delay + jitter)
    time.sleep(actual)


def get_ids_from_api(keyword: str, max_pages: int) -> list[int]:
    """
    Use the SOAP API to search for law IDs by keyword.
    """
    try:
        from api_client import LegislatieAPIClient
    except ImportError:
        print("ERROR: suds-community is not installed.")
        return []

    client = LegislatieAPIClient()
    laws = client.get_all_ids(keyword=keyword, max_pages=max_pages)
    ids = [int(law.Id) for law in laws if hasattr(law, "Id")]
    print(f"  API found {len(ids)} IDs for keyword '{keyword}'.")
    return ids


def run_pipeline(law_ids: list[int], delay: float = 3.0):
    """
    Main scraping loop.
    Parameters:
      law_ids  — list of integer law IDs to scrape
      delay    — base seconds to wait between requests (default 3.0)
                 Actual wait = delay ± 50% random jitter
    """
    ensure_data_dir()
    already_done = load_already_scraped()
    pending = [id_ for id_ in law_ids if id_ not in already_done]

    print(f"\n{'='*60}")
    print(f"  Laws requested:      {len(law_ids)}")
    print(f"  Already in dataset:  {len(already_done)}")
    print(f"  To scrape now:       {len(pending)}")
    print(f"  Base delay:          {delay}s (±50% jitter)")
    print(f"{'='*60}\n")

    if not pending:
        print("Nothing to do — all requested IDs are already scraped.")
        print(f"Delete {LAWS_FILE} to force a re-scrape.")
        return

    success_count = 0
    failed_ids = []

    for law_id in tqdm(pending, desc="Scraping", unit="law"):
        law = scrape_law(law_id)

        if law is None:
            failed_ids.append(law_id)
            polite_sleep(delay)
            continue
        law = clean_law(law)

        if law["article_count"] == 0:
            print(f"  WARNING: ID {law_id} has 0 articles after cleaning. "
                  f"Adding to failed list.")
            failed_ids.append(law_id)
            polite_sleep(delay)
            continue

        append_jsonl(LAWS_FILE, {
            "id":            law["id"],
            "title":         law["title"],
            "url":           law["url"],
            "article_count": law["article_count"],
            "articles":      law["articles"],
        })

        for article in law["articles"]:
            append_jsonl(ARTICLES_FILE, {
                "law_id":         law["id"],
                "law_title":      law["title"],
                "article_number": article["number"],
                "text":           article["text"],
                "chunk": (
                    f"{law['title']}\n"
                    f"{article['number']}\n\n"
                    f"{article['text']}"
                ),
            })

        success_count += 1
        polite_sleep(delay)

    print(f"\n{'='*60}")
    print(f"  Successfully scraped: {success_count} laws")
    print(f"  Failed:               {len(failed_ids)} laws")

    if failed_ids:
        print(f"\n  Failed IDs: {failed_ids}")
        with open(FAILED_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(str(i) for i in failed_ids))
        print(f"  Saved to {FAILED_FILE} — retry later with:")
        print(f"    python pipeline.py --ids-file {FAILED_FILE}")

    print(f"\n  Output files:")
    if LAWS_FILE.exists():
        print(f"    {LAWS_FILE}      ({LAWS_FILE.stat().st_size // 1024:,} KB)")
    if ARTICLES_FILE.exists():
        print(f"    {ARTICLES_FILE}  ({ARTICLES_FILE.stat().st_size // 1024:,} KB)")

    print(f"\n  Next step: python indexer.py")
    print(f"{'='*60}\n")


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Scrape Romanian laws from legislatie.just.ro.\n\n"
            "Examples:\n"
            "  python pipeline.py --ids 109567 175630      # Codul Muncii + Codul Civil\n"
            "  python pipeline.py --important              # All 9 important law codes\n"
            "  python pipeline.py --keyword muncă          # Search API by keyword\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--ids",
        nargs="+",
        type=int,
        metavar="ID",
        help="Scrape specific law IDs (skip the API step entirely).",
    )
    parser.add_argument(
        "--important",
        action="store_true",
        help=(
            "Scrape the 9 most important Romanian law codes "
            "(Codul Muncii, Codul Civil, Codul Penal, etc.)."
        ),
    )
    parser.add_argument(
        "--ids-file",
        type=str,
        metavar="FILE",
        help="Path to a text file with one law ID per line.",
    )
    parser.add_argument(
        "--keyword",
        type=str,
        default=None,
        help="Search keyword for the SOAP API (e.g. 'muncă', 'concediu').",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Max API result pages to fetch (default: 5, ~250 laws per page).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=3.0,
        help=(
            "Base seconds to wait between requests (default: 3.0). "
            "Actual wait = delay ± 50%% random jitter. "
            "Use 4.0+ for large batches."
        ),
    )

    return parser.parse_args()


def main():
    args = parse_args()

    if args.important:
        law_ids = list(IMPORTANT_LAW_IDS.keys())
        print("Scraping the 9 most important Romanian law codes:")
        for law_id, name in IMPORTANT_LAW_IDS.items():
            print(f"  {law_id} — {name}")

    elif args.ids:
        law_ids = args.ids
        print(f"Scraping {len(law_ids)} specified IDs: {law_ids}")

    elif args.ids_file:
        path = Path(args.ids_file)
        if not path.exists():
            print(f"ERROR: File not found: {path}")
            sys.exit(1)
        with open(path, encoding="utf-8") as f:
            law_ids = [
                int(line.strip())
                for line in f
                if line.strip().isdigit()
            ]
        print(f"Loaded {len(law_ids)} IDs from {path}.")

    elif args.keyword:
        print(f"Searching SOAP API for keyword: '{args.keyword}'...")
        law_ids = get_ids_from_api(args.keyword, args.max_pages)
        if not law_ids:
            print("No IDs found. Try a different keyword or use --ids directly.")
            sys.exit(1)

    else:
        print("No input specified.\n")
        for law_id, name in IMPORTANT_LAW_IDS.items():
            print(f"  {law_id:>8}  {name}")
        sys.exit(0)
    run_pipeline(law_ids, delay=args.delay)


if __name__ == "__main__":
    main()