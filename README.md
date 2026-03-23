# News Digest Agent

A zero-dependency Python agent that fetches news across four sectors, summarizes each with Claude, and emails you a digest three times a day via GitHub Actions.

---

## API Keys Required

| Service | Where to Get It | Cost |
|---|---|---|
| **NewsAPI** | [newsapi.org](https://newsapi.org) — create free account | Free tier: 100 req/day (plenty for 3 runs × 4 sectors = 12 req/day) |
| **Anthropic (Claude)** | [console.anthropic.com](https://console.anthropic.com) → API Keys | ~$0.25/month (Haiku at ~$0.001/1K tokens × ~600 tokens × 12 calls/day × 30 days) |
| **Gmail** | Your existing Gmail account + App Password (see below) | Free |

**Estimated total cost: ~$0.25–$0.30/month**

---

## Gmail App Password Setup

Gmail requires an App Password (not your regular password) when sending via SMTP.

1. Go to your Google Account → **Security**
2. Enable **2-Step Verification** if not already on
3. Go to **Security → 2-Step Verification → App passwords** (scroll to the bottom)
   - Direct link: `myaccount.google.com/apppasswords`
4. Select app: **Mail** — Select device: **Other** → type `NewsDigestAgent`
5. Click **Generate** — copy the 16-character password (no spaces)
6. Use that password as your `GMAIL_APP_PASS` secret

---

## Initial Setup

### 1. Clone / create the repository

```bash
# Create a new GitHub repo at github.com/new (name it "news-agent"), then:
git init
git add .
git commit -m "Initial commit: news digest agent"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/news-agent.git
git push -u origin main
```

### 2. Add GitHub Secrets

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | Value |
|---|---|
| `NEWSAPI_KEY` | Your NewsAPI key from newsapi.org |
| `ANTHROPIC_API_KEY` | Your Anthropic API key (starts with `sk-ant-...`) |
| `GMAIL_USER` | Your full Gmail address (e.g. `you@gmail.com`) |
| `GMAIL_APP_PASS` | The 16-character App Password from Gmail (no spaces) |
| `TO_EMAIL` | Email address to receive digests (can be same as GMAIL_USER) |

### 3. Verify the workflow is enabled

Go to your repo → **Actions** tab → confirm `News Digest` workflow is listed and enabled.

---

## Schedule

The workflow runs automatically at these times (Pacific Time):

| Slot | PT Time | UTC Cron |
|---|---|---|
| Morning Brief | 6:00 AM | `0 13 * * *` |
| Midday Update | 10:00 AM | `0 17 * * *` |
| Afternoon Digest | 2:00 PM | `0 21 * * *` |

> **Note:** GitHub Actions cron schedules can run a few minutes late during high load. This is normal.

---

## Manual Test Run

1. Go to your repo → **Actions** tab
2. Click **News Digest** in the left sidebar
3. Click **Run workflow** (top right)
4. Optionally enter a slot override: `morning`, `midday`, or `afternoon`
5. Click the green **Run workflow** button
6. Watch the run logs — you should receive an email within ~60 seconds

---

## Customizing Sectors

Edit the `SECTORS` dict at the top of `agent.py`:

```python
SECTORS = {
    "Your Sector Name": [
        "primary keyword",
        "secondary keyword",
        "third keyword",
        # ...
    ],
    # add or remove sectors as needed
}
```

- The **sector name** becomes the email section header
- The query sent to NewsAPI is: `"Sector Name" OR "keyword1" OR "keyword2"` (top 2 keywords used)
- Each sector fetches up to 10 articles

---

## Running Locally

```bash
export NEWSAPI_KEY="your-key"
export ANTHROPIC_API_KEY="sk-ant-..."
export GMAIL_USER="you@gmail.com"
export GMAIL_APP_PASS="your16charpassword"
export TO_EMAIL="recipient@example.com"
export DIGEST_SLOT="morning"

python agent.py
```

No `pip install` needed — only Python stdlib is used.

---

## Cost Estimate Breakdown

| Item | Calculation | Monthly Cost |
|---|---|---|
| NewsAPI | Free tier, 12 calls/day | $0.00 |
| Claude Haiku | ~600 tokens × 4 sectors × 3 runs × 30 days = ~216K tokens | ~$0.03 input + ~$0.22 output ≈ **$0.25** |
| Gmail SMTP | Free | $0.00 |
| GitHub Actions | Free tier (2,000 min/month — agent runs in ~30s) | $0.00 |
| **Total** | | **~$0.25–$0.30/month** |

---

## Project Structure

```
news-agent/
├── agent.py                        # Main script — all logic lives here
├── .github/
│   └── workflows/
│       └── digest.yml              # GitHub Actions schedule + dispatch
└── README.md                       # This file
```
