import re
import unicodedata

try:
    import ftfy
    HAS_FTFY = True
except ImportError:
    HAS_FTFY = False
    print("Tip: pip install ftfy")


DIACRITIC_MAP = {
    "ş": "ș",
    "ţ": "ț",
    "Ş": "Ș",
    "Ţ": "Ț",
    "\u015e": "Ș",
    "\u015f": "ș",
    "\u0162": "Ț",
    "\u0163": "ț",
}


_BOILERPLATE_PATTERNS = [
    r"A fost lansata versiunea Beta.*?corect\.",
    r"Datorita faptului ca folositi.*?corect!",
    r"De ce sa actualizez browserul\?.*?securitate\.",
    r"Browserele invechite.*?securitate\.",
    r"Reveniti in topul paginii",
    r"Forma printabilă",
    r"EMITENT\s*\n.*?\n",
    r"Publicat în\s*\n.*?\n",
    r"MONITORUL OFICIAL.*?\n",
    r"Portal Legislativ",
    r"legislatie\.just\.ro",
    r"©\s*\d{4}.*?rezervate\.",
    r"Conținutul acestui material.*?României\.",
]

_BOILERPLATE_RE = re.compile(
    "|".join(_BOILERPLATE_PATTERNS),
    re.IGNORECASE | re.DOTALL,
)

_BLACKLIST_LINES = {
    "Reveniti in topul paginii",
    "Forma printabilă",
    "EMITENT",
    "PARLAMENTUL ROMÂNIEI",
    "PARLAMENTUL",
    "GUVERNUL",
    "GUVERNUL ROMÂNIEI",
    "PREȘEDINTELE ROMÂNIEI",
    "MONITORUL OFICIAL",
    "Portal Legislativ",
    "Pagina de start",
}

_AMENDMENT_KEYWORDS = [
    "abrogată",
    "abrogat",
    "respinsă",
    "modificat prin",
    "completat prin",
    "înlocuit prin",
    "republicată",
]


def fix_encoding(text: str) -> str:
    """
    Fix garbled characters caused by wrong encoding detection.
       e.g.: "ș" instead of "Å£" or "ÅŸ"
    """
    if HAS_FTFY:
        return ftfy.fix_text(text)
    return unicodedata.normalize("NFC", text)


def fix_diacritics(text: str) -> str:
    """
    Replace legacy cedilla forms with the correct comma-below forms.
    """
    for wrong, correct in DIACRITIC_MAP.items():
        text = text.replace(wrong, correct)
    return text


def remove_boilerplate(text: str) -> str:
    return _BOILERPLATE_RE.sub("", text)


def normalize_whitespace(text: str) -> str:
    """
    Tidy up whitespace without destroying paragraph structure.
    """
    text = text.replace("\t", " ").replace("\xa0", " ")
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_amendment_only(text: str) -> bool:
    """
    Return True if this article contains only amendment references.
    An amendment-only article looks like:
        "Articolul 5 a fost modificat prin Legea 40/2011.
         Articolul 5 a fost completat prin OUG 53/2017."
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return True

    amendment_line_count = sum(
        1 for line in lines
        if any(keyword in line.lower() for keyword in _AMENDMENT_KEYWORDS)
    )

    return (amendment_line_count / len(lines)) > 0.5


def clean_article_text(text: str) -> str:
    """
    Clean the text of a single article.
    """
    # Step 1: Remove blacklisted whole-line phrases
    lines = text.split("\n")
    lines = [
        line for line in lines
        if not any(phrase in line for phrase in _BLACKLIST_LINES)
    ]
    text = "\n".join(lines)

    # Step 2: Remove law title headers that the portal injects
    text = re.sub(
        r"LEGE\s+nr\.\s*\d+.*?(?=\n[A-ZĂÎȘȚ\(]|\Z)",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(
        r"ORDONAN[ȚT][AĂ]\s+(?:DE\s+URGEN[ȚT][AĂ]\s+)?nr\.\s*\d+.*?(?=\n[A-ZĂÎȘȚ\(]|\Z)",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Step 3: Remove footnote marker blocks at the top
    text = re.sub(r"^\*+\).*?\n\n", "", text, flags=re.DOTALL)

    # Step 4: Remove footnote separator lines and everything after them
    text = re.sub(r"[-─]{5,}.*", "", text, flags=re.DOTALL)

    # Step 5: Clean up whitespace
    return normalize_whitespace(text)


def clean_law(law: dict) -> dict:
    """
    Apply all cleaning steps to a scraped law dictionary.
    """
    title = re.sub(r"\s+", " ", law.get("title", "")).strip()

    raw = law.get("raw_text", "")
    raw = fix_encoding(raw)
    raw = fix_diacritics(raw)
    raw = remove_boilerplate(raw)
    raw = normalize_whitespace(raw)

    cleaned_articles = []

    for article in law.get("articles", []):
        text = article.get("text", "")
        text = fix_encoding(text)
        text = fix_diacritics(text)
        text = clean_article_text(text)

        if len(text) < 80:
            continue

        if is_amendment_only(text):
            continue

        cleaned_articles.append({
            "number": article["number"],
            "text":   text,
        })

    print(f"  Cleaned: {len(law.get('articles', []))} articles → "
          f"{len(cleaned_articles)} kept after filtering.")

    return {
        **law,
        "title":         title,
        "raw_text":      raw,
        "articles":      cleaned_articles,
        "article_count": len(cleaned_articles),
    }
