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
    "Commercial Real Estate": [
        "commercial real estate",
        "CRE",
        "REIT",
        "cap rate",
        "multifamily",
        "JLL",
        "CBRE",
        "office market",
    ],
    "Finance & Markets": [
        "interest rates",
        "Federal Reserve",
        "S&P 500",
        "private equity",
        "hedge fund",
        "bond market",
        "inflation",
    ],
    "Technology": [
        "artificial intelligence",
        "AI startup",
        "venture capital",
        "SaaS",
        "fintech",
        "proptech",
    ],
    "San Diego / Local": [
        "San Diego",
        "San Diego housing",
        "California real estate",
        "Southern California economy",
        "San Diego business",
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

# Domains with free full-text content — passed to NewsAPI as an allowlist
ALLOWED_DOMAINS = (
    "reuters.com,cnbc.com,marketwatch.com,apnews.com,businessinsider.com,"
    "fortune.com,thestreet.com,investopedia.com,housingwire.com,globest.com,"
    "bisnow.com,costar.com,commercialobserver.com"
)

# Paywalled domains — filtered out after fetching
BLOCKED_DOMAINS = ("wsj.com", "bloomberg.com", "ft.com", "nytimes.com", "barrons.com")


# ---------------------------------------------------------------------------
# News fetching
# ---------------------------------------------------------------------------

def fetch_articles(sector_name: str, keywords: list[str], api_key: str) -> list[dict]:
    """Fetch up to ARTICLES_PER_SECTOR articles for a sector from NewsAPI."""
    # Use sector name + top 2 keywords as the query
    query_parts = [sector_name] + keywords[:2]
    query = " OR ".join(f'"{p}"' for p in query_parts)

    params = {
        "q": query,
        "domains": ALLOWED_DOMAINS,
        "sortBy": "publishedAt",
        "pageSize": ARTICLES_PER_SECTOR,
        "language": "en",
        "apiKey": api_key,
    }
    url = f"{NEWSAPI_URL}?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(url, headers={"User-Agent": "NewsDigestAgent/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  [!] NewsAPI HTTP error for '{sector_name}': {e.code} {e.reason}")
        return []
    except Exception as e:
        print(f"  [!] NewsAPI error for '{sector_name}': {e}")
        return []

    articles = data.get("articles", [])
    # Filter out removed articles and paywalled domains
    articles = [
        a for a in articles
        if a.get("title") and a["title"] != "[Removed]"
        and not any(blocked in a.get("url", "") for blocked in BLOCKED_DOMAINS)
    ]
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
        # Strip the NewsAPI "[N chars]" truncation suffix from content
        if " [+" in content:
            content = content[:content.rfind(" [+")]
        url = a.get("url", "")
        body = " ".join(filter(None, [title, description, content]))
        lines.append(f"{i}. [{source}] ({date})\n   {body}\n   {url}")
    return "\n\n".join(lines)


def summarize_sector(sector_name: str, articles: list[dict], api_key: str) -> str:
    """Call Claude to summarize a sector's articles. Returns HTML-safe markdown text."""
    if not articles:
        return "<p><em>No articles found for this sector.</em></p>"

    article_text = build_article_text(articles)
    prompt = (
        f"You are a concise financial news analyst. Analyze these {len(articles)} recent news articles "
        f"about '{sector_name}' and return a structured digest in exactly this format:\n\n"
        "SUMMARY: [2-3 sentence executive summary of the most important developments]\n\n"
        "KEY POINTS:\n"
        "• [key point with source name in parentheses]\n"
        "• [key point with source name in parentheses]\n"
        "• [key point with source name in parentheses]\n"
        "(3-5 bullet points total)\n\n"
        "SO WHAT: [1-2 sentence insight on why this matters or what to watch]\n\n"
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
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        return data["content"][0]["text"]
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  [!] Anthropic HTTP {e.code} error for '{sector_name}':")
        print(f"      {body}")
        return "<p><em>Summarization failed.</em></p>"
    except Exception as e:
        print(f"  [!] Anthropic error for '{sector_name}': {e}")
        traceback.print_exc()
        return "<p><em>Summarization failed.</em></p>"


# ---------------------------------------------------------------------------
# Email rendering
# ---------------------------------------------------------------------------

def text_to_html(text: str) -> str:
    """Convert Claude's plain-text digest format into simple HTML."""
    html_parts = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("SUMMARY:"):
            content = line[len("SUMMARY:"):].strip()
            html_parts.append(f'<p><strong>Summary:</strong> {content}</p>')
        elif line.startswith("KEY POINTS:"):
            html_parts.append('<p><strong>Key Points:</strong></p><ul>')
        elif line.startswith("•") or line.startswith("-"):
            content = line.lstrip("•- ").strip()
            html_parts.append(f'<li>{content}</li>')
            # Close ul on next non-bullet will be handled below
        elif line.startswith("SO WHAT:"):
            # Close any open ul
            if html_parts and html_parts[-1] != '</ul>':
                # Check if we have open ul
                for j in range(len(html_parts) - 1, -1, -1):
                    if html_parts[j] == '<ul>':
                        html_parts.append('</ul>')
                        break
                    elif html_parts[j] == '</ul>':
                        break
            content = line[len("SO WHAT:"):].strip()
            html_parts.append(
                f'<p style="background:#f0f7e0;border-left:3px solid #c8f060;'
                f'padding:8px 12px;margin:12px 0;">'
                f'<strong>So What:</strong> {content}</p>'
            )
        else:
            # Close any open ul before adding paragraph
            in_list = False
            for j in range(len(html_parts) - 1, -1, -1):
                if html_parts[j] == '<ul>':
                    in_list = True
                    break
                elif html_parts[j] == '</ul>':
                    break
            if in_list:
                html_parts.append('</ul>')
            html_parts.append(f'<p>{line}</p>')

    # Close any trailing open ul
    in_list = False
    for j in range(len(html_parts) - 1, -1, -1):
        if html_parts[j] == '<ul>':
            in_list = True
            break
        elif html_parts[j] == '</ul>':
            break
    if in_list:
        html_parts.append('</ul>')

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
