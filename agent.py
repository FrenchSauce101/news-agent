"""
News Digest Agent
Fetches news across multiple sectors, summarizes with Claude, and emails a digest.
"""

import json
import os
import smtplib
import ssl
import traceback
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ---------------------------------------------------------------------------
# Sectors to track — edit this dict to customize what you follow
# ---------------------------------------------------------------------------
SECTORS = {
    # Keywords are sent to NewsAPI as quoted OR terms.
    # The first 15 are used per query — put broadest terms first.

    # ------------------------------------------------------------------ #
    #  BREAKING NEWS — geopolitical conflicts & macro economic shocks     #
    # ------------------------------------------------------------------ #
    "Breaking News": [
        "war",
        "military strike",
        "sanctions",
        "geopolitical",
        "trade war",
        "tariff",
        "oil supply",
        "global recession",
        "debt crisis",
        "ceasefire",
        "invasion",
        "conflict zone",
        "regime change",
        "coup",
        "civil war",
        "trade embargo",
        "export controls",
        "energy crisis",
        "OPEC production cut",
        "oil embargo",
        "sovereign debt",
        "currency crisis",
        "central bank intervention",
        "emergency rate cut",
        "supply chain disruption",
        "commodity shock",
        "inflation surge",
        "stagflation crisis",
        "NATO",
        "G7 summit",
        "G20 summit",
        "IMF warning",
        "World Bank",
        "Security Council",
        "Russia Ukraine",
        "Middle East conflict",
        "Gaza",
        "Israel Iran",
        "China Taiwan",
        "North Korea",
        "South China Sea",
        "nuclear threat",
        "terrorist attack",
        "cyberattack infrastructure",
        "humanitarian crisis",
        "refugee crisis",
        "government collapse",
        "political instability",
        "election crisis",
        "government shutdown",
        "debt ceiling",
        "sovereign default",
        "bank run",
        "financial contagion",
        "hyperinflation",
        "Brent crude",
        "gas prices spike",
        "food prices",
        "protest riot",
    ],

    # ------------------------------------------------------------------ #
    #  COMMERCIAL REAL ESTATE                                             #
    # ------------------------------------------------------------------ #
    "Commercial Real Estate": [
        "real estate",
        "commercial property",
        "office market",
        "REIT",
        "multifamily",
        "industrial real estate",
        "office vacancy",
        "property values",
        "cap rate",
        "commercial mortgage",
        "retail real estate",
        "real estate investment",
        "office space",
        "data center",
        "warehouse",
        "sublease",
        "coworking",
        "net lease",
        "CMBS",
        "real estate developer",
        "property market",
        "apartment market",
        "logistics real estate",
        "office towers",
        "real estate deal",
        "building sale",
        "sale leaseback",
        "ground lease",
        "triple net lease",
        "mixed use development",
        "affordable housing",
        "build to rent",
        "single family rental",
        "self storage",
        "senior housing",
        "life sciences real estate",
        "medical office",
        "shopping mall",
        "industrial park",
        "last mile logistics",
        "cold storage",
        "flex space",
        "office conversion",
        "adaptive reuse",
        "real estate fund",
        "real estate portfolio",
        "distressed real estate",
        "loan maturity",
        "real estate refinancing",
        "real estate private equity",
        "mezzanine debt",
        "preferred equity real estate",
        "construction starts",
        "building permits",
        "absorption rate",
        "net operating income",
        "occupancy rate",
        "lease renewal",
        "JLL",
        "CBRE",
        "Cushman Wakefield",
        "Blackstone real estate",
        "Brookfield real estate",
        "Starwood real estate",
        "commercial lending",
        "rent growth",
        "ESG real estate",
        "green building",
        "housing market",
        "property tax",
        "zoning",
    ],

    # ------------------------------------------------------------------ #
    #  FINANCE & MARKETS                                                  #
    # ------------------------------------------------------------------ #
    "Finance & Markets": [
        "interest rates",
        "Federal Reserve",
        "S&P 500",
        "stock market",
        "bond market",
        "inflation",
        "yield curve",
        "Treasury yield",
        "private equity",
        "hedge fund",
        "mortgage rates",
        "10-year Treasury",
        "Fed funds rate",
        "rate hike",
        "rate cut",
        "quantitative tightening",
        "monetary policy",
        "fiscal stimulus",
        "GDP growth",
        "recession risk",
        "unemployment rate",
        "consumer confidence",
        "retail sales",
        "CPI inflation",
        "PCE inflation",
        "core inflation",
        "stagflation",
        "dollar index",
        "emerging markets",
        "credit spread",
        "high yield spread",
        "leveraged finance",
        "earnings season",
        "earnings growth",
        "profit margin",
        "market valuation",
        "Nasdaq composite",
        "Dow Jones",
        "Russell 2000",
        "VIX volatility",
        "short squeeze",
        "ETF flows",
        "institutional buying",
        "margin debt",
        "oil price",
        "gold price",
        "Bitcoin",
        "cryptocurrency",
        "bank earnings",
        "regional bank",
        "bank stress test",
        "financial regulation",
        "SEC enforcement",
        "FDIC",
        "equity market",
        "ISM manufacturing",
        "PMI",
        "producer price index",
        "yield curve inversion",
        "balance sheet reduction",
        "options expiration",
        "fund flows",
    ],

    # ------------------------------------------------------------------ #
    #  CAPITAL MARKETS                                                    #
    # ------------------------------------------------------------------ #
    "Capital Markets": [
        "investment banking",
        "capital markets",
        "IPO",
        "bond offering",
        "equity offering",
        "leveraged buyout",
        "M&A",
        "debt issuance",
        "high yield bond",
        "leveraged loan",
        "syndicated loan",
        "CLO",
        "securitization",
        "credit default swap",
        "interest rate swap",
        "Goldman Sachs",
        "Morgan Stanley",
        "JPMorgan",
        "convertible bond",
        "secondary offering",
        "follow-on offering",
        "rights offering",
        "investment grade bond",
        "junk bond",
        "credit facility",
        "revolving credit",
        "term loan",
        "CDO",
        "asset backed security",
        "structured finance",
        "total return swap",
        "Bank of America Merrill Lynch",
        "Citigroup",
        "Deutsche Bank",
        "UBS",
        "Barclays",
        "merger acquisition",
        "takeover bid",
        "hostile takeover",
        "acquisition premium",
        "strategic acquisition",
        "restructuring",
        "bankruptcy",
        "Chapter 11",
        "debt restructuring",
        "distressed debt",
        "activist investor",
        "proxy fight",
        "shareholder activism",
        "SPAC merger",
        "equity research",
        "analyst rating",
        "price target",
        "credit rating",
        "Moody's",
        "Fitch downgrade",
        "market liquidity",
        "block trade",
        "prime brokerage",
        "margin call",
        "deleveraging",
        "dividend recap",
        "share buyback",
        "return of capital",
    ],

    # ------------------------------------------------------------------ #
    #  TECHNOLOGY                                                         #
    # ------------------------------------------------------------------ #
    "Technology": [
        "artificial intelligence",
        "large language model",
        "generative AI",
        "AI startup",
        "AI investment",
        "venture capital",
        "tech IPO",
        "cloud computing",
        "cybersecurity",
        "semiconductor",
        "NVIDIA",
        "machine learning",
        "ChatGPT",
        "OpenAI",
        "Google DeepMind",
        "Microsoft AI",
        "Meta AI",
        "AI chips",
        "AI data center",
        "foundation model",
        "AI regulation",
        "SaaS",
        "fintech",
        "proptech",
        "startup funding",
        "tech earnings",
        "AWS",
        "Azure",
        "Google Cloud",
        "data breach",
        "ransomware",
        "chip shortage",
        "AMD",
        "Intel foundry",
        "TSMC",
        "Series A",
        "Series B",
        "unicorn valuation",
        "tech layoffs",
        "automation",
        "robotics",
        "autonomous vehicle",
        "electric vehicle software",
        "biotech AI",
        "digital health",
        "insurtech",
        "blockchain",
        "Web3",
        "augmented reality",
        "5G deployment",
        "quantum computing",
        "digital transformation",
        "enterprise AI",
        "open source",
        "developer tools",
        "platform economy",
        "API economy",
        "software platform",
        "hyperscaler",
        "data privacy",
    ],
}

SLOT_LABELS = {
    "morning": "Morning Brief",
    "midday": "Midday Update",
    "afternoon": "Afternoon Digest",
}

NEWSAPI_URL = "https://newsapi.org/v2/everything"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
ARTICLES_PER_SECTOR = 10

# NewsAPI source IDs — free sources only. Must not be combined with "domains".
SECTOR_SOURCES = {
    "Breaking News":          "reuters,associated-press,abc-news,cbs-news,cnbc",
    "Commercial Real Estate": "cnbc,reuters,associated-press,abc-news,cbs-news",
    "Finance & Markets":      "cnbc,reuters,associated-press,abc-news,cbs-news",
    "Capital Markets":        "cnbc,reuters,associated-press,abc-news,cbs-news",
    "Technology":             "techcrunch,the-verge,cnbc,reuters,associated-press",
}


# ---------------------------------------------------------------------------
# News fetching
# ---------------------------------------------------------------------------

def fetch_articles(sector_name: str, keywords: list[str], api_key: str) -> list[dict]:
    """Fetch up to ARTICLES_PER_SECTOR articles for a sector from NewsAPI."""
    sources = SECTOR_SOURCES.get(sector_name)  # None for San Diego

    # Build query from keywords directly — do NOT prepend the sector name.
    # First 15 keywords are used; put broadest terms first in the SECTORS dict.
    query = " OR ".join(f'"{kw}"' for kw in keywords[:15])

    # Limit to the last 24 hours so each digest surfaces today's news only
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")

    params = {
        "q": query,
        "from": since,
        "sortBy": "publishedAt",
        "pageSize": ARTICLES_PER_SECTOR,
        "language": "en",
        "apiKey": api_key,
    }
    # NOTE: NewsAPI forbids combining "sources" with "domains" or "country"
    if sources:
        params["sources"] = sources

    print(f"  [debug] Query: {query!r}  sources={sources}")
    url = f"{NEWSAPI_URL}?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(url, headers={"User-Agent": "NewsDigestAgent/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  [!] NewsAPI HTTP {e.code} error for '{sector_name}': {body}")
        return []
    except Exception as e:
        print(f"  [!] NewsAPI error for '{sector_name}': {e}")
        return []

    # NewsAPI returns HTTP 200 with status=error for API-level problems (e.g. bad params)
    if data.get("status") == "error":
        print(f"  [!] NewsAPI API error for '{sector_name}': {data.get('message')}")
        return []

    articles = data.get("articles", [])
    print(f"  [debug] NewsAPI returned {len(articles)} raw articles.")
    articles = [a for a in articles if a.get("title") and a["title"] != "[Removed]"]
    return articles


def deduplicate(articles: list[dict]) -> list[dict]:
    """Remove duplicate articles by URL."""
    seen = set()
    unique = []
    for a in articles:
        url = a.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(a)
    return unique


# ---------------------------------------------------------------------------
# AI summarization
# ---------------------------------------------------------------------------

def build_article_text(articles: list[dict]) -> str:
    """Format articles into a compact text block for the prompt."""
    lines = []
    for i, a in enumerate(articles, 1):
        title = a.get("title") or ""
        source = a.get("source", {}).get("name", "Unknown")
        date = (a.get("publishedAt") or "")[:10]
        description = a.get("description") or ""
        content = a.get("content") or ""
        # Strip the NewsAPI "[+N chars]" truncation suffix from content
        if " [+" in content:
            content = content[:content.rfind(" [+")]
        url = a.get("url", "")
        body = " ".join(filter(None, [title, description, content]))
        # Cap each article at 500 chars to keep the overall prompt manageable
        body = body[:500]
        lines.append(f"{i}. [{source}] ({date})\n   {body}\n   {url}")
    return "\n\n".join(lines)


def has_usable_content(article: dict) -> bool:
    """Return True if the article has enough text to be worth summarizing."""
    description = article.get("description") or ""
    content = article.get("content") or ""
    # Require at least 60 chars of combined description + content
    return len(description) + len(content) >= 60


def summarize_sector(sector_name: str, articles: list[dict], api_key: str) -> str:
    """Call Claude to summarize a sector's articles. Returns HTML-safe markdown text."""
    if not articles:
        return "<p><em>No articles found for this sector.</em></p>"

    # Drop articles with no readable text (paywalled sources return empty description/content)
    usable = [a for a in articles if has_usable_content(a)]
    print(f"  [debug] {len(usable)}/{len(articles)} articles have usable content.")
    if not usable:
        return "<p><em>No readable article content available for this sector (all sources paywalled or empty).</em></p>"

    article_text = build_article_text(usable)
    print(f"  [debug] Prompt article block is {len(article_text)} chars.")
    prompt = (
        f"You are a concise financial news analyst. Analyze these {len(usable)} recent news articles "
        f"about '{sector_name}' and return a digest using EXACTLY this structure and labels — "
        "no markdown, no asterisks, no ALL CAPS, no deviations:\n\n"
        "Summary: [2-3 sentence executive summary of the most important developments]\n\n"
        "Key Points:\n"
        "• [Full sentence key point. (Source Name)]\n"
        "• [Full sentence key point. (Source Name)]\n"
        "• [Full sentence key point. (Source Name)]\n"
        "Include 3-5 bullet points. Each bullet must end with the source name in parentheses.\n\n"
        "So What?: [1-2 sentence insight on what this means for investors and what to watch next]\n\n"
        "Important: Use exactly the labels 'Summary:', 'Key Points:', and 'So What?:' — "
        "do not use bold markers, asterisks, or any other formatting.\n\n"
        f"Articles:\n{article_text}"
    )

    payload = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": 600,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        ANTHROPIC_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    key_preview = api_key[:8] + "..." if api_key else "(empty)"
    print(f"  [debug] Anthropic key preview: {key_preview}")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        return data["content"][0]["text"]
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  [!] Anthropic HTTP {e.code} error for '{sector_name}': {body}")
        return f"<p><em>Summarization failed — Anthropic HTTP {e.code}: {body[:300]}</em></p>"
    except Exception as e:
        print(f"  [!] Anthropic error for '{sector_name}': {e}")
        traceback.print_exc()
        return f"<p><em>Summarization failed — {e}</em></p>"


# ---------------------------------------------------------------------------
# Email rendering
# ---------------------------------------------------------------------------

def _close_open_ul(html_parts: list[str]) -> None:
    """Append </ul> if there is an unclosed <ul> in html_parts."""
    for item in reversed(html_parts):
        if item == '<ul>':
            html_parts.append('</ul>')
            return
        if item == '</ul>':
            return


def text_to_html(text: str) -> str:
    """Convert Claude's plain-text digest into clean HTML.

    Handles any capitalisation variant Claude might return
    (Summary / SUMMARY / **Summary:**) and strips stray markdown asterisks.
    """
    html_parts = []

    for line in text.splitlines():
        line = line.strip()
        # Strip markdown bold markers that Claude occasionally adds
        line = line.replace("**", "")
        if not line:
            continue

        lower = line.lower()

        if lower.startswith("summary:"):
            content = line[len("summary:"):].strip()
            html_parts.append(f'<p><strong>Summary:</strong> {content}</p>')

        elif lower.startswith("key points:"):
            html_parts.append('<p><strong>Key Points:</strong></p><ul>')

        elif line.startswith("•") or line.startswith("-") or line.startswith("*"):
            content = line.lstrip("•-* ").strip()
            html_parts.append(f'<li>{content}</li>')

        elif lower.startswith("so what"):
            _close_open_ul(html_parts)
            # Strip any label variant: "So What?:", "So What:", "SO WHAT:"
            colon_pos = line.find(":")
            content = line[colon_pos + 1:].strip() if colon_pos != -1 else line
            html_parts.append(
                '<p style="background:#f0f7e0;border-left:3px solid #c8f060;'
                'padding:8px 12px;margin:12px 0;">'
                f'<strong>So What?</strong> {content}</p>'
            )

        else:
            _close_open_ul(html_parts)
            html_parts.append(f'<p>{line}</p>')

    _close_open_ul(html_parts)
    return "\n".join(html_parts)


def build_html_email(slot: str, sections: list[tuple[str, list[dict], str]]) -> str:
    """
    Build the full HTML email body.
    sections: list of (sector_name, articles, summary_text)
    """
    label = SLOT_LABELS.get(slot, slot.title())
    pt_tz = timezone(timedelta(hours=-7))  # PDT; adjust to -8 for PST
    now_pt = datetime.now(pt_tz)
    timestamp = now_pt.strftime("%A, %B %-d, %Y · %-I:%M %p PT")

    sector_html_parts = []
    for sector_name, articles, summary in sections:
        summary_html = text_to_html(summary)
        article_links = ""
        for a in articles[:5]:  # Show top 5 source links
            title = a.get("title", "Article")[:80]
            url = a.get("url", "#")
            source = a.get("source", {}).get("name", "")
            source_span = f' <span style="color:#888;">— {source}</span>' if source else ""
            article_links += (
                f'<div style="margin:4px 0;font-size:12px;">'
                f'<a href="{url}" style="color:#4a90d9;text-decoration:none;">{title}</a>'
                f'{source_span}'
                f'</div>'
            )

        sector_html_parts.append(f"""
        <div style="margin:24px 0;padding:20px;background:#fff;
                    border-radius:6px;border-left:4px solid #c8f060;
                    box-shadow:0 1px 4px rgba(0,0,0,0.08);">
          <h2 style="margin:0 0 12px;font-size:18px;color:#1a1a2e;">{sector_name}</h2>
          <div style="font-size:14px;color:#333;line-height:1.6;">
            {summary_html}
          </div>
          {"<hr style='border:none;border-top:1px solid #eee;margin:14px 0;'>" + article_links if article_links else ""}
        </div>
        """)

    sectors_block = "\n".join(sector_html_parts)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{label}</title>
</head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:Georgia,serif;">
  <div style="max-width:680px;margin:0 auto;padding:20px;">

    <!-- Header -->
    <div style="background:#1a1a2e;border-radius:8px 8px 0 0;padding:28px 30px;text-align:center;">
      <h1 style="margin:0;color:#c8f060;font-size:26px;letter-spacing:1px;">{label}</h1>
      <p style="margin:8px 0 0;color:#a0aec0;font-size:13px;">{timestamp}</p>
    </div>

    <!-- Body -->
    <div style="background:#f4f6f9;padding:16px;">
      {sectors_block}
    </div>

    <!-- Footer -->
    <div style="background:#1a1a2e;border-radius:0 0 8px 8px;padding:16px 30px;text-align:center;">
      <p style="margin:0;color:#718096;font-size:11px;">
        Generated by News Digest Agent · Powered by NewsAPI &amp; Claude
      </p>
    </div>

  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------

def send_email(subject: str, html_body: str, gmail_user: str, gmail_pass: str, to_email: str) -> None:
    """Send HTML email via Gmail SMTP SSL."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(gmail_user, gmail_pass)
        server.sendmail(gmail_user, to_email, msg.as_string())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # Load config from environment
    newsapi_key = os.environ["NEWSAPI_KEY"]
    anthropic_key = os.environ["ANTHROPIC_API_KEY"]
    gmail_user = os.environ["GMAIL_USER"]
    gmail_pass = os.environ["GMAIL_APP_PASS"]
    to_email = os.environ.get("TO_EMAIL", gmail_user)
    slot = os.environ.get("DIGEST_SLOT", "morning").lower()

    label = SLOT_LABELS.get(slot, slot.title())
    print(f"=== News Digest Agent — {label} ===")

    sections = []
    for sector_name, keywords in SECTORS.items():
        print(f"\n[{sector_name}]")

        print(f"  Fetching articles...")
        articles = fetch_articles(sector_name, keywords, newsapi_key)
        articles = deduplicate(articles)
        print(f"  Found {len(articles)} unique articles.")

        print(f"  Summarizing with Claude...")
        summary = summarize_sector(sector_name, articles, anthropic_key)
        sections.append((sector_name, articles, summary))
        print(f"  Done.")

    print("\nBuilding HTML email...")
    html_body = build_html_email(slot, sections)

    subject = f"[{label}] News Digest — {datetime.now().strftime('%b %-d, %Y')}"
    print(f"Sending email to {to_email}...")
    send_email(subject, html_body, gmail_user, gmail_pass, to_email)
    print("Email sent successfully.")


if __name__ == "__main__":
    main()
