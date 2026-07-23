# 🏠 Personal Housing Feed

One RSS feed + email digest of **new rental listings that match your exact criteria**, aggregated across Zillow, Apartments.com, Zumper, HotPads, Craigslist, local brokerages, and more — running free, 24/7, on GitHub.

---

## How it works (the whole idea in 5 lines)

```
   You create "saved search" ALERTS on each rental site
            │  (each site emails you its own new matches)
            ▼
   All those alert emails land in ONE dedicated Gmail
            │
            ▼
   GitHub Actions runs aggregate.py a few times a day  ──►  emails you a DIGEST of what's new
            │  (reads inbox, parses listings, filters to your specs, de-dupes)
            ▼
   Writes feed.xml  ──►  served free by GitHub Pages  ──►  you subscribe in any RSS reader
```

**Why this design?** Zillow/Redfin/etc. block scraping and it breaks constantly. But every one of them will happily *email you* new matches for free. So we let them do the finding, and we do the **aggregating, filtering, de-duplicating, and re-publishing** into one clean feed. That's the "email-to-RSS bridge."

---

## What's in this folder

| File | What it is |
|---|---|
| `aggregate.py` | The engine: reads the inbox, filters, de-dupes, writes the feed, emails the digest |
| `parsers.py` | Pulls price/beds/baths/URL out of alert emails + Craigslist RSS |
| `config.yaml` | **Your settings** — criteria, price, beds, keywords, sources. Edit anytime. |
| `.github/workflows/housing.yml` | The schedule that runs it all automatically |
| `requirements.txt` | Python dependencies |
| `test_local.py` | Offline self-test (proves parsing/filter/de-dupe work) |

---

# Setup — 6 steps (~30–40 min, one time)

## Step 1 — Lock in your criteria

Open `config.yaml` and fill in the `criteria:` block. Example:

```yaml
criteria:
  city_terms: ["Austin", "78704", "78745", "South Congress"]
  max_price: 2600
  min_beds: 2
  min_baths: 1
  any_keywords: ["dog", "pet", "pets"]      # at least one must appear
  exclude_keywords: ["income restricted", "senior", "55+", "sublet"]
```

> **Just tell me your specs in chat and I'll fill this in for you** and generate the ready-to-click saved-search URLs in Step 2.

---

## Step 2 — Make a dedicated inbox + turn on saved-search alerts

**2a. Create a dedicated Gmail** (e.g. `adam.housing@gmail.com`). Keeps alerts out of your main inbox and gives the script a clean place to read from. *(You can instead use your normal Gmail + a filter that labels alerts "Housing" — set `imap.folder: "Housing"` in config.)*

**2b. On each site: run your search → save it → enable email alerts → point them at that Gmail.** Where the button lives:

| Site | How to turn on alert emails |
|---|---|
| **Zillow** | Run search → **Save search** → toggle **Email** notifications |
| **Apartments.com** | Run search → **Save Search** (heart) → set email frequency to *Immediately* |
| **Zumper** | Run search → **Save search** → enable email alerts |
| **HotPads** | Run search → **Save Search** → email alerts on |
| **Realtor.com / Redfin / Trulia** | Save search → email notifications (works for rentals too) |
| **Craigslist** | Make a free account → run search → **save search** → open **Searches** tab → tick **Alert** ✅ |
| **Local brokerages** | Most have a "Save search / email me new listings" on their rentals page. Send me the brokerage names and I'll find the exact links. |

> If a site can only email your *normal* address, add a Gmail filter there: `Settings → Filters → forward matching mail to` your housing address (or just label it and set `imap.folder`).

**⚠️ Facebook Marketplace:** no email alerts and no RSS, plus aggressive anti-bot — it can't be automated reliably. Options: (a) skip it, (b) check it manually, or (c) some local Facebook housing groups let you turn on post notifications. I left it out of the automated pipeline on purpose so it doesn't break the rest.

---

## Step 3 — Get a Gmail App Password (so the script can read the inbox)

1. On the dedicated Gmail: **Google Account → Security → turn on 2-Step Verification** (required).
2. Go to **https://myaccount.google.com/apppasswords** → create one named `housing-feed`.
3. Copy the **16-character password** (no spaces). You'll paste it into GitHub in Step 4.

*(Gmail IMAP is on by default now. If you use Advanced Protection or a Workspace account where an admin blocked app passwords, use a regular personal Gmail instead.)*

---

## Step 4 — Put the code on GitHub

1. Create a free account at **github.com**.
2. **New repository** → name it `housing-feed` → **Public** (required for free Pages + unlimited Actions) → Create.
3. Upload every file from this folder (drag-and-drop into the repo's **Add file → Upload files**, including the `.github` folder — or `git push` if you're comfortable).
4. Add your secrets: repo **Settings → Secrets and variables → Actions → New repository secret**. Create three:

   | Secret name | Value |
   |---|---|
   | `IMAP_USER` | your dedicated Gmail address |
   | `IMAP_PASSWORD` | the 16-char app password from Step 3 |
   | `SMTP_TO` | where digests go (e.g. `adamegrace@gmail.com`) |

5. Open the **Actions** tab → click **I understand my workflows, enable them**.

> Secrets are encrypted and never appear in logs. The app password only grants mail access to this one Gmail and can be revoked anytime.

---

## Step 5 — Turn on GitHub Pages (this hosts your feed URL)

1. Repo **Settings → Pages → Build and deployment → Source: Deploy from a branch → `main` / `/ (root)` → Save.**
2. Your feed will live at:
   `https://<your-username>.github.io/housing-feed/feed.xml`
3. Put that exact URL into `config.yaml` under `feed.link:` and commit the change.

---

## Step 6 — Run it, then subscribe

1. **Actions** tab → **housing-feed** → **Run workflow** (manual first run).
2. It will read any alert emails already waiting, build `feed.xml`, and email you a digest. Check:
   - the run is green ✅,
   - `feed.xml` updated in the repo,
   - a `[Housing]` digest arrived (if there were new matches).
3. **Subscribe** to your feed URL in any RSS reader — [Feedly](https://feedly.com), [Inoreader](https://inoreader.com), or NetNewsWire (free, Mac). Done. 🎉

From now on it runs itself ~7am / 12pm / 5pm / 9pm Central (a few times a day, per your choice).

---

## Tuning it later

Everything is in `config.yaml` — change your max price, add a keyword, tighten location — commit, and the next run uses the new rules. No code edits ever needed.

- `strict_location: true` → hard-drop anything not mentioning a `city_terms` entry.
- `require_keywords` → ALL must appear. `any_keywords` → at least one. `exclude_keywords` → any kills it.
- Add/remove sites by adding their saved-search alerts (Step 2) — the parser already recognizes the major domains via `listing_url_patterns`.

## Good to know

- **Scheduled runs can lag 5–30 min** under GitHub load — normal, not broken.
- **GitHub disables schedules after 60 days of no commits** — the script writes a `last_run.txt` heartbeat every run, which commits and resets that timer, so it stays alive.
- **If a site revamps its email template** and listings from it stop showing, tell me the source and I'll adjust its pattern — the parser is generic so this is rare.
- **Cost: $0.** Public repos get unlimited Actions minutes + free Pages.

## No-code fallback (if you don't want GitHub at all)

Use [kill-the-newsletter.com](https://kill-the-newsletter.com): create one inbox per saved search, point each site's alert at the address it gives you, and subscribe to the RSS feeds it generates in your reader. You lose the single merged/de-duped feed, the custom filtering, and the digest email — but it's zero setup.

---

*Built to lean on each site's own alert emails rather than scraping — that's what keeps it reliable and within their terms.*
