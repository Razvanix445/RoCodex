import re
import time
import requests
from bs4 import BeautifulSoup

URL_PATTERNS = [
    "https://legislatie.just.ro/Public/DetaliiDocument/{}",
    "https://legislatie.just.ro/Public/DetaliiDocumentAfis/{}",
]
BASE_URL = URL_PATTERNS[0]

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://legislatie.just.ro/",
    "Connection": "keep-alive",
})


def _fetch_single_url(url: str, retries: int = 3) -> requests.Response | None:
    """
    Try to GET one URL with retries and rate-limit handling.
    Returns the Response object on success, None on permanent failure.
    """
    for attempt in range(retries):
        try:
            resp = SESSION.get(url, timeout=20)

            if resp.status_code == 429:
                wait = 60 * (attempt + 1)
                print(f"\n  Rate limited (429). Waiting {wait}s...")
                time.sleep(wait)
                continue

            if resp.status_code == 403:
                return None

            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding
            return resp

        except requests.exceptions.Timeout:
            time.sleep(2 ** attempt)
        except requests.exceptions.ConnectionError:
            time.sleep(2 ** attempt)
        except requests.exceptions.HTTPError:
            time.sleep(2 ** attempt)

    return None


def fetch_law_page(law_id: int) -> tuple[BeautifulSoup, str] | tuple[None, None]:
    """
    Download the HTML page for one law, trying both URL patterns automatically.

    The portal uses two different URL patterns:
      - DetaliiDocument/{id}     — works for most actualizat (A) versions
      - DetaliiDocumentAfis/{id} — works for republicat (R) and older versions

    We try DetaliiDocument first. If it returns a page with < 500 chars of
    actual text content, we assume it's a redirect/error and try the Afis URL.

    Returns (BeautifulSoup, url_used) on success, or (None, None) on failure.
    """
    for url_pattern in URL_PATTERNS:
        url = url_pattern.format(law_id)
        resp = _fetch_single_url(url)

        if resp is None:
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        body = soup.find("body")
        text_preview = body.get_text() if body else ""
        if len(text_preview.strip()) >= 500:
            return soup, url
        print(f"\n  ↻ {url_pattern.split('/')[5]} returned empty page, "
              f"trying alternate URL pattern...")

    print(f"\n  ✗ Both URL patterns failed for ID {law_id}. Skipping.")
    return None, None


def extract_title(soup: BeautifulSoup) -> str:
    """
    Pull the law's title from the HTML.
    The page <title> tag contains things like:
        "LEGE 53 28/06/2003 - Portal Legislativ"
        "CODUL CIVIL din 17 iulie 2009 - Portal Legislativ"
    We strip the " - Portal Legislativ" suffix and return the rest.
    """
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)
        title = title.replace(" - Portal Legislativ", "").strip()
        if title:
            return title

    for tag in ["h1", "h2", "h3"]:
        heading = soup.find(tag)
        if heading:
            text = heading.get_text(strip=True)
            if len(text) > 5:
                return text

    return "Unknown"


def extract_raw_text(soup: BeautifulSoup) -> str:
    """
    Strip all HTML and return the plain text content of the law.

    We remove:
      - <script> and <style> tags (JavaScript and CSS — not law text)
      - <nav> tags (site navigation menus)
      - <footer> and <header> tags (site chrome)
      - <form> tags (search boxes, login forms)
      - Tags with class names that suggest UI elements, not content

    Then we use BeautifulSoup's get_text() to extract the remaining text,
    using newlines as separators so article structure is preserved.
    """
    for tag in soup(["script", "style", "nav", "footer", "header", "form"]):
        tag.decompose()

    for tag in soup.find_all(class_=re.compile(
        r"(menu|navbar|breadcrumb|pagination|sidebar|cookie|banner|btn|button)",
        re.IGNORECASE
    )):
        tag.decompose()

    content = (
        soup.find("div", class_=re.compile(r"(content|document|text|lege)", re.IGNORECASE))
        or soup.find("body")
    )
    if not content:
        return ""

    text = content.get_text(separator="\n")
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def split_into_articles(raw_text: str) -> list[dict]:
    """
    Cut the full law text into individual articles.
    Steps:
      1. Find every article header using a regex
      2. Each header's text ends where the NEXT header begins
      3. Return a list of {"number": ..., "text": ...} dicts
    """
    article_pattern = re.compile(
        r"^[\+\s]*"
        r"((?:Articolul|ARTICOLUL)\s+"
        r"(\d+(?:\^\d+)?|UNIC|[IVXLC]{1,6}))"
        r"(?!\s+(?:din\b|alin\b|lit\b|pct\b|teza\b))",
        re.MULTILINE,
    )

    matches = list(article_pattern.finditer(raw_text))

    if not matches:
        return [{"number": "Articolul 1", "text": raw_text.strip()}]

    articles = []
    for i, match in enumerate(matches):
        header = match.group(1).strip()

        text_start = match.end()

        text_end = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)

        body = raw_text[text_start:text_end].strip()

        if not body:
            continue

        body_single_line = " ".join(body.split())
        if re.match(r"^[\(\[\*\s]*[Aa]brogat[\)\]\*\s\.]*$", body_single_line):
            continue

        articles.append({
            "number": header,
            "text":   body,
        })

    return articles


def scrape_law(law_id: int) -> dict | None:
    """
    Full pipeline for one law ID:
      1. Download the HTML page
      2. Extract the title
      3. Extract the raw plain text
      4. Split into individual articles
      5. Return a structured dict
    Returns None if the page couldn't be fetched or was empty.
    """
    print(f"\n  → Fetching ID {law_id}...")

    soup, url = fetch_law_page(law_id)
    if soup is None:
        return None

    raw_text = extract_raw_text(soup)

    if not raw_text or len(raw_text) < 200:
        print(f"  Skipping ID {law_id}. The page looks empty after text extraction.")
        return None

    title    = extract_title(soup)
    articles = split_into_articles(raw_text)

    print(f"  '{title}' — {len(articles)} articles found.")
    print(f"    URL: {url}")

    return {
        "id":            law_id,
        "title":         title,
        "url":           url,
        "article_count": len(articles),
        "articles":      articles,
        "raw_text":      raw_text,
    }


if __name__ == "__main__":
    result = scrape_law(128646)

    if result:
        print(f"\n{'='*60}")
        print(f"Title:    {result['title']}")
        print(f"URL:      {result['url']}")
        print(f"Articles: {result['article_count']}")
        print(f"\nFirst 3 articles:")
        for art in result["articles"][:3]:
            print(f"\n  [{art['number']}]")
            print(f"  {art['text'][:200]}...")
    else:
        print("Failed to scrape. Check your internet connection.")