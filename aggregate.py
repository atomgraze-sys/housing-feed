#!/usr/bin/env python3
"""
aggregate.py — the engine.

Each run:
  1. Reads unread listing-alert emails from a dedicated Gmail inbox (IMAP).
  2. Pulls Craigslist search results directly via native RSS.
  3. Normalizes every listing, filters to your criteria (config.yaml), and
     deduplicates against everything seen before (listings.json).
  4. Writes feed.xml (served publicly via GitHub Pages) so any RSS reader can subscribe.
  5. Emails you a digest of only the brand-new listings.

Secrets come from environment variables (set as GitHub Actions secrets):
  IMAP_USER      - the dedicated Gmail address (e.g. you.housing@gmail.com)
  IMAP_PASSWORD  - a Gmail *App Password* (needs 2-Step Verification on)
  SMTP_TO        - where to send the digest (defaults to IMAP_USER)
Everything else lives in config.yaml.
"""

import os
import re
import sys
import json
import imaplib
import email
import smtplib
import datetime as dt
from email.message import EmailMessage
from email.header import decode_header, make_header

import yaml
from feedgen.feed import FeedGenerator

import parsers

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.yaml")
STORE_PATH = os.path.join(HERE, "listings.json")
FEED_PATH = os.path.join(HERE, "feed.xml")
HEARTBEAT_PATH = os.path.join(HERE, "last_run.txt")

UTC = dt.timezone.utc


def now():
    return dt.datetime.now(UTC)


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_store():
    try:
        with open(STORE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_store(store):
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, sort_keys=True)


# ---------------- email intake ----------------
def _decode(s):
    try:
        return str(make_header(decode_header(s)))
    except Exception:
        return s or ""


def _html_from_message(msg):
    """Return the best HTML (or text) body from an email.message.Message."""
    html, text = None, None
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if part.get("Content-Disposition", "").startswith("attachment"):
                continue
            try:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or "utf-8"
                body = payload.decode(charset, errors="replace")
            except Exception:
                continue
            if ctype == "text/html" and html is None:
                html = body
            elif ctype == "text/plain" and text is None:
                text = body
    else:
        try:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="replace") if payload else ""
        except Exception:
            body = ""
        if msg.get_content_type() == "text/html":
            html = body
        else:
            text = body
    # Wrap plain text so the same anchor-based parser can still find URLs.
    if html is None and text:
        html = "<html><body><pre>{}</pre></body></html>".format(text)
    return html


def fetch_email_listings(cfg):
    user = os.environ.get("IMAP_USER")
    pw = os.environ.get("IMAP_PASSWORD")
    if not user or not pw:
        print("… no IMAP_USER / IMAP_PASSWORD set — skipping email intake.")
        return []

    host = cfg.get("imap", {}).get("host", "imap.gmail.com")
    folder = cfg.get("imap", {}).get("folder", "INBOX")
    patterns = cfg.get("listing_url_patterns", [])
    listings = []

    try:
        M = imaplib.IMAP4_SSL(host)
        M.login(user, pw)
    except Exception as e:
        print(f"!! IMAP login failed: {e}")
        return []

    try:
        M.select(f'"{folder}"')
        typ, data = M.search(None, "UNSEEN")
        ids = data[0].split() if data and data[0] else []
        print(f"… {len(ids)} unread message(s) in {folder}")
        for num in ids:
            typ, msg_data = M.fetch(num, "(RFC822)")
            if typ != "OK" or not msg_data or not msg_data[0]:
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            html = _html_from_message(msg)
            found = parsers.parse_email_html(html, patterns)
            for L in found:
                L.setdefault("_via", _decode(msg.get("From", "")))
            listings.extend(found)
            # Mark as read so we don't reprocess next run.
            M.store(num, "+FLAGS", "\\Seen")
    except Exception as e:
        print(f"!! IMAP read error: {e}")
    finally:
        try:
            M.logout()
        except Exception:
            pass

    print(f"… parsed {len(listings)} listing link(s) from email")
    return listings


# ---------------- craigslist intake ----------------
def fetch_craigslist_listings(cfg):
    src = cfg.get("sources", {}).get("craigslist", {})
    if not src.get("enabled"):
        return []
    out = []
    for url in src.get("feeds", []) or []:
        try:
            got = parsers.parse_craigslist_feed(url)
            print(f"… craigslist: {len(got)} item(s) from {url[:60]}…")
            out.extend(got)
        except Exception as e:
            print(f"!! craigslist feed failed ({url[:60]}…): {e}")
    return out


# ---------------- filtering ----------------
# Portland uses directional address prefixes (SE Hawthorne, NE Alberta). We match the
# uppercase abbreviations (address style) case-sensitively to avoid false hits like
# "sw" inside "answer", plus the spelled-out forms case-insensitively.
_QUAD_ABBR_RE = re.compile(r"\b(NE|NW|SE|SW)\b")
_QUAD_WORD_RE = re.compile(r"\b(north\s*east|north\s*west|south\s*east|south\s*west)\b", re.I)
_QUAD_WORD_MAP = {"northeast": "NE", "northwest": "NW", "southeast": "SE", "southwest": "SW"}


def detect_quadrants(text):
    """Return the set of Portland quadrants mentioned, e.g. {'SE', 'NE'}."""
    found = set()
    if not text:
        return found
    for m in _QUAD_ABBR_RE.findall(text):
        found.add(m.upper())
    for m in _QUAD_WORD_RE.findall(text):
        found.add(_QUAD_WORD_MAP[re.sub(r"\s+", "", m).lower()])
    return found


# Numbered-avenue detection (east–west position on Portland's grid). We only accept a
# number when it carries an ordinal ("55th") or is followed by "Ave", so house numbers
# and "900 sqft" don't get mistaken for an avenue.
_AVE_DIR_RE = re.compile(r"(?:NE|NW|SE|SW)\s+(\d{1,3})(?:st|nd|rd|th)\b", re.I)
_AVE_WORD_RE = re.compile(r"\b(\d{1,3})(?:st|nd|rd|th)?\s+(?:ave\b|avenue\b)", re.I)


def parse_avenues(text):
    """Return every numbered avenue mentioned, e.g. 'SE 55th Ave' -> [55]."""
    nums = []
    if not text:
        return nums
    for m in _AVE_DIR_RE.findall(text) + _AVE_WORD_RE.findall(text):
        try:
            nums.append(int(m))
        except (TypeError, ValueError):
            pass
    return sorted(set(nums))


def passes(listing, c):
    p = listing.get("price")
    if p is not None:
        if c.get("min_price") and p < c["min_price"]:
            return False
        if c.get("max_price") and p > c["max_price"]:
            return False
    b = listing.get("beds")
    if b is not None and c.get("min_beds") is not None and b < c["min_beds"]:
        return False
    ba = listing.get("baths")
    if ba is not None and c.get("min_baths") is not None and ba < c["min_baths"]:
        return False
    sq = listing.get("sqft")
    if sq is not None and c.get("min_sqft") and sq < c["min_sqft"]:
        return False

    hay = " ".join(
        str(listing.get(k, "")) for k in ("title", "description", "location", "url")
    ).lower()

    for kw in c.get("exclude_keywords", []) or []:
        if kw.lower() in hay:
            return False
    req = c.get("require_keywords", []) or []
    if req and not all(kw.lower() in hay for kw in req):
        return False
    anyk = c.get("any_keywords", []) or []
    if anyk and not any(kw.lower() in hay for kw in anyk):
        return False

    # Location is a *soft* filter by default: saved searches already constrain it,
    # and alert emails don't always include city text. Only hard-drop if strict.
    ct = c.get("city_terms", []) or []
    if ct and c.get("strict_location"):
        if not any(t.lower() in hay for t in ct):
            return False

    # Original-case text for address-level checks (quadrant + avenue).
    raw = " ".join(
        str(listing.get(k, "")) for k in ("title", "location", "description", "url")
    )

    # Quadrant filter: keep only listings in an allowed Portland quadrant (e.g. NE/SE).
    # Listings that mention no quadrant at all are kept (lenient).
    aq = c.get("require_quadrants") or []
    if aq:
        allowed = {x.upper() for x in aq}
        quads = detect_quadrants(raw)
        if quads and not (quads & allowed):
            return False

    # Avenue cap: drop listings east of a max numbered avenue (e.g. > SE/NE 55th).
    # Lenient — if no avenue is detectable in the text, the listing is kept.
    mav = c.get("max_avenue")
    if mav:
        aves = parse_avenues(raw)
        if aves and max(aves) > mav:
            return False

    return True


# ---------------- feed ----------------
def label(listing):
    bits = []
    if listing.get("price"):
        bits.append(f"${listing['price']:,}/mo")
    b = listing.get("beds")
    if b is not None:
        bits.append("Studio" if b == 0 else f"{b:g}bd")
    if listing.get("baths") is not None:
        bits.append(f"{listing['baths']:g}ba")
    if listing.get("sqft"):
        bits.append(f"{listing['sqft']:,}ft²")
    head = " · ".join(bits)
    src = listing.get("source", "")
    title = listing.get("title", "")
    return f"{head} — {title} [{src}]" if head else f"{title} [{src}]"


def build_feed(store, cfg):
    feed = cfg.get("feed", {})
    fg = FeedGenerator()
    fg.id(feed.get("link", "https://example.com/feed.xml"))
    fg.title(feed.get("title", "Housing Feed"))
    fg.link(href=feed.get("link", "https://example.com/feed.xml"), rel="self")
    fg.description(feed.get("description", "Aggregated new housing listings"))
    fg.language("en")

    items = sorted(store.values(), key=lambda x: x.get("first_seen", ""), reverse=True)
    max_items = int(feed.get("max_items", 200))
    for L in items[:max_items]:
        fe = fg.add_entry()
        fe.id(L["id"])
        fe.title(label(L))
        fe.link(href=L["url"])
        desc = L.get("description", "") or ""
        loc = L.get("location", "")
        body = f"{desc}"
        if loc:
            body += f"<br><b>Area:</b> {loc}"
        body += f'<br><a href="{L["url"]}">View listing →</a>'
        fe.description(body)
        try:
            fs = dt.datetime.fromisoformat(L["first_seen"])
            if fs.tzinfo is None:
                fs = fs.replace(tzinfo=UTC)
            fe.pubDate(fs)
        except Exception:
            pass
    fg.rss_file(FEED_PATH, pretty=True)
    print(f"… wrote {FEED_PATH} with {min(len(items), max_items)} item(s)")


# ---------------- digest email ----------------
def send_digest(new_items, cfg, total=None, snapshot=False):
    user = os.environ.get("IMAP_USER")
    pw = os.environ.get("IMAP_PASSWORD")
    to = os.environ.get("SMTP_TO") or user
    if not (user and pw and to) or not new_items:
        return
    rows = []
    for L in new_items:
        rows.append(
            f'<li><a href="{L["url"]}">{label(L)}</a>'
            + (f' <span style="color:#666">— {L.get("location")}</span>' if L.get("location") else "")
            + "</li>"
        )
    # If we're showing a capped slice of a larger batch, say so.
    if snapshot:
        heading = f"Current listings — {len(new_items)} matching your criteria"
        subject = f"[Housing] Current snapshot: {len(new_items)} listings"
    elif total and total > len(new_items):
        heading = f"Cheapest {len(new_items)} of {total} new listings"
        subject = f"[Housing] {total} new — cheapest {len(new_items)}"
    else:
        heading = f"{len(new_items)} new listing(s)"
        subject = f"[Housing] {len(new_items)} new listing(s)"
    feed_link = cfg.get("feed", {}).get("link", "")
    html = (
        f"<h2>{heading}</h2>"
        f"<ul>{''.join(rows)}</ul>"
        + (f'<p>Full feed: <a href="{feed_link}">{feed_link}</a></p>' if feed_link else "")
    )
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to
    msg.set_content(f"{heading}. Open in an HTML-capable client.")
    msg.add_alternative(html, subtype="html")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(user, pw)
            s.send_message(msg)
        print(f"… emailed digest to {to}")
    except Exception as e:
        print(f"!! digest email failed: {e}")


# ---------------- housekeeping ----------------
def prune(store, cfg):
    days = int(cfg.get("feed", {}).get("retention_days", 30))
    cutoff = now() - dt.timedelta(days=days)
    keep = {}
    for k, v in store.items():
        try:
            fs = dt.datetime.fromisoformat(v.get("first_seen"))
            if fs.tzinfo is None:
                fs = fs.replace(tzinfo=UTC)
        except Exception:
            fs = now()
        if fs >= cutoff:
            keep[k] = v
    return keep


def snapshot_digest(store, cfg):
    """On-demand: email ALL current listings already in the store, cheapest first.
    Read-only — does NOT ingest email, mark anything read, or modify the feed/store,
    so it never interferes with the regular new-listings digest."""
    items = list(store.values())
    fcfg = cfg.get("feed", {})
    if fcfg.get("digest_sort", "cheapest") == "cheapest":
        items.sort(key=lambda L: (L.get("price") is None, L.get("price") or 0))
    else:
        items.sort(key=lambda L: L.get("first_seen", ""), reverse=True)
    limit = int(fcfg.get("current_digest_limit", 0) or 0)
    if limit:
        items = items[:limit]
    print(f"== snapshot: emailing {len(items)} current listing(s)")
    send_digest(items, cfg, snapshot=True)
    return 0


def main():
    cfg = load_yaml(CONFIG_PATH)
    crit = cfg.get("criteria", {})
    store = load_store()

    # Snapshot mode (second workflow): email everything currently in the store, no ingest.
    if os.environ.get("DIGEST_SCOPE", "new").lower() == "current":
        return snapshot_digest(store, cfg)

    candidates = []
    candidates += fetch_email_listings(cfg)
    candidates += fetch_craigslist_listings(cfg)

    new_items = []
    for L in candidates:
        if L["id"] in store:
            continue
        if not passes(L, crit):
            continue
        L["first_seen"] = now().isoformat()
        store[L["id"]] = L
        new_items.append(L)

    print(f"== {len(new_items)} new listing(s) after filter+dedupe")

    store = prune(store, cfg)
    save_store(store)
    build_feed(store, cfg)

    # Digest = a short, curated slice of THIS run's new listings (the full feed keeps
    # everything). Default: the cheapest 20, price low -> high.
    fcfg = cfg.get("feed", {})
    if fcfg.get("digest_sort", "cheapest") == "cheapest":
        digest_items = sorted(
            new_items, key=lambda L: (L.get("price") is None, L.get("price") or 0)
        )
    else:  # "newest"
        digest_items = list(new_items)
    limit = int(fcfg.get("digest_limit", 0) or 0)
    capped = digest_items[:limit] if limit else digest_items
    send_digest(capped, cfg, total=len(new_items))

    with open(HEARTBEAT_PATH, "w", encoding="utf-8") as f:
        f.write(now().isoformat() + "\n")  # guarantees a commit -> keeps Actions alive

    return 0


if __name__ == "__main__":
    sys.exit(main())
