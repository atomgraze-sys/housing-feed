"""
parsers.py — turn listing-alert emails and Craigslist RSS into normalized listings.

Design note: email templates from Zillow/Apartments.com/etc. change often, so we do
NOT hard-code each site's exact HTML. Instead we use a generic, resilient strategy:
find every link that matches a known listing-URL pattern, then read the surrounding
text of that link's "card" to pull price / beds / baths / sqft with regex. This keeps
working even when the sites tweak their layouts.
"""

import re
import hashlib
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup
import feedparser

# ---------- field extractors ----------
PRICE_RE = re.compile(r"\$\s?([\d,]{3,7})")
BEDS_RE = re.compile(r"(\d+(?:\.\d)?)\s*(?:bd|beds?|bedrooms?|br)\b", re.I)
BATHS_RE = re.compile(r"(\d+(?:\.\d)?)\s*(?:ba|baths?|bathrooms?)\b", re.I)
SQFT_RE = re.compile(r"([\d,]{3,6})\s*(?:sq\s?\.?\s?ft|sqft|ft2|ft²)", re.I)
STUDIO_RE = re.compile(r"\bstudio\b", re.I)


def _to_num(s):
    try:
        return float(str(s).replace(",", ""))
    except Exception:
        return None


def parse_price(text):
    m = PRICE_RE.search(text or "")
    return int(_to_num(m.group(1))) if m else None


def parse_beds(text):
    if not text:
        return None
    # An explicit bedroom count ("2 br", "1 bed") is more specific than the word
    # "studio", so it wins. Only treat as a studio when no number is present.
    m = BEDS_RE.search(text)
    if m:
        return _to_num(m.group(1))
    if STUDIO_RE.search(text):
        return 0.0
    return None


def parse_baths(text):
    m = BATHS_RE.search(text or "")
    return _to_num(m.group(1)) if m else None


def parse_sqft(text):
    m = SQFT_RE.search(text or "")
    return int(_to_num(m.group(1))) if m else None


# ---------- url helpers ----------
def clean_url(href):
    """Strip query string + fragment (tracking params) so the same listing dedupes."""
    try:
        p = urlparse(href.strip())
        if not p.scheme:
            return href.strip()
        path = p.path.rstrip("/")
        return urlunparse((p.scheme, p.netloc.lower(), path, "", "", "")) or href.strip()
    except Exception:
        return href.strip()


def listing_id(url):
    return hashlib.sha1(clean_url(url).encode("utf-8")).hexdigest()[:16]


def domain_of(url):
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


# ---------- normalization ----------
def normalize(d):
    """Guarantee a consistent listing shape and attach a stable id."""
    url = clean_url(d.get("url", ""))
    out = {
        "id": listing_id(url),
        "url": url,
        "title": (d.get("title") or "").strip() or url,
        "price": d.get("price"),
        "beds": d.get("beds"),
        "baths": d.get("baths"),
        "sqft": d.get("sqft"),
        "source": d.get("source") or domain_of(url),
        "location": (d.get("location") or "").strip(),
        "description": (d.get("description") or "").strip()[:400],
    }
    return out


# ---------- email parsing (generic, config-driven) ----------
def _container_text(anchor, max_up=4):
    """Walk up a few parents to capture the listing card's surrounding text."""
    node = anchor
    best = anchor.get_text(" ", strip=True)
    for _ in range(max_up):
        if node.parent is None:
            break
        node = node.parent
        txt = node.get_text(" ", strip=True)
        if "$" in txt or len(txt) > 80:
            best = txt
            if "$" in txt:
                break
    return best


def parse_email_html(html, patterns):
    """
    patterns: list of regex strings that match listing-detail URLs for enabled sites.
    Returns a list of normalized listings found in the email body.
    """
    if not html:
        return []
    compiled = [re.compile(p, re.I) for p in patterns]
    soup = BeautifulSoup(html, "lxml")
    seen_urls = set()
    listings = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not any(c.search(href) for c in compiled):
            continue
        cu = clean_url(href)
        if cu in seen_urls:
            continue
        seen_urls.add(cu)

        ctx = _container_text(a)
        title = a.get_text(" ", strip=True)
        if not title or len(title) < 4:
            img = a.find("img")
            if img and img.get("alt"):
                title = img["alt"].strip()
        if not title or len(title) < 4:
            title = ctx[:80]

        listings.append(
            normalize(
                {
                    "url": cu,
                    "title": title,
                    "price": parse_price(ctx),
                    "beds": parse_beds(ctx),
                    "baths": parse_baths(ctx),
                    "sqft": parse_sqft(ctx),
                    "source": domain_of(cu),
                    "description": ctx,
                }
            )
        )
    return listings


# ---------- Craigslist native RSS ----------
def parse_craigslist_feed(feed_url):
    """Craigslist search pages expose RSS. Titles look like:
    '$1,800 / 2br - 900ft2 - Cute bungalow (south austin)'."""
    parsed = feedparser.parse(feed_url)
    out = []
    for e in parsed.entries:
        title = e.get("title", "") or ""
        url = e.get("link", "") or ""
        if not url:
            continue
        summary = ""
        if e.get("summary"):
            summary = BeautifulSoup(e["summary"], "lxml").get_text(" ", strip=True)
        loc = ""
        m = re.search(r"\(([^)]+)\)\s*$", title)
        if m:
            loc = m.group(1)
        out.append(
            normalize(
                {
                    "url": url,
                    "title": title,
                    "price": parse_price(title),
                    "beds": parse_beds(title),
                    "sqft": parse_sqft(title),
                    "source": "craigslist.org",
                    "location": loc,
                    "description": summary or title,
                }
            )
        )
    return out
