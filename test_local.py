"""Offline test harness — proves parsing/filter/dedupe/feed work without any inbox."""
import parsers
from aggregate import passes, build_feed, prune, now

# 1) A realistic (simplified) Zillow-style alert email: cards with image + text links.
SAMPLE = """
<html><body>
<table>
 <tr><td>
   <a href="https://www.zillow.com/homedetails/123-Elm-St-Austin-TX-78704/1234_zpid/?utm=abc">
     <img alt="123 Elm St, Austin, TX 78704"></a>
   <div><a href="https://www.zillow.com/homedetails/123-Elm-St-Austin-TX-78704/1234_zpid/?utm=abc">
     $2,150/mo · 2 bd · 1 ba · 900 sqft — 123 Elm St, Austin, TX 78704</a></div>
 </td></tr>
 <tr><td>
   <a href="https://www.apartments.com/the-monroe-austin-tx/abc123/">
     The Monroe</a>
   <div>$1,875/mo &middot; 1 bed &middot; 1 bath &middot; 650 sq ft &middot; South Congress</div>
 </td></tr>
 <tr><td>
   <a href="https://www.zillow.com/homedetails/9-Rich-Rd-Austin-TX-78701/9999_zpid/">
     Luxury tower</a>
   <div>$4,500/mo · 3 bd · 2 ba — income restricted community</div>
 </td></tr>
 <tr><td>
   <a href="https://unsubscribe.example.com/stop">Unsubscribe</a>
 </td></tr>
</body></html>
"""

PATTERNS = [
    r"zillow\.com/(homedetails|b|apartments|community)/",
    r"apartments\.com/[^\"']+/[a-z0-9]",
]

print("=== Email parsing ===")
found = parsers.parse_email_html(SAMPLE, PATTERNS)
for L in found:
    print(f"  {L['price']!s:>6} | beds={L['beds']} baths={L['baths']} sqft={L['sqft']} | {L['source']} | {L['title'][:40]}")
assert len(found) == 3, f"expected 3 listings, got {len(found)} (unsubscribe link must be ignored)"
prices = sorted(x["price"] for x in found)
assert prices == [1875, 2150, 4500], prices
print("  OK: 3 listings parsed, unsubscribe link ignored\n")

print("=== Craigslist RSS parsing (synthetic) ===")
import feedparser, types
CL_RSS = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>$1,800 / 2br - 900ft2 - Cute bungalow (south austin)</title>
<link>https://austin.craigslist.org/apa/d/austin-cute-bungalow/7700000001.html</link>
<description>Great spot near SoCo</description></item>
<item><title>$950 / 1br - studio flat (downtown)</title>
<link>https://austin.craigslist.org/apa/d/austin-studio/7700000002.html</link></item>
</channel></rss>"""
open("/tmp/cl.xml", "w").write(CL_RSS)
cl = parsers.parse_craigslist_feed("file:///tmp/cl.xml")
for L in cl:
    print(f"  {L['price']!s:>6} | beds={L['beds']} | {L['location']} | {L['title'][:40]}")
assert len(cl) == 2 and cl[0]["price"] == 1800 and cl[0]["beds"] == 2.0
print("  OK: craigslist titles parsed\n")

print("=== Filter (max_price 3000, min_beds 1, exclude 'income restricted') ===")
crit = {"max_price": 3000, "min_beds": 1, "min_baths": 1,
        "exclude_keywords": ["income restricted"]}
kept = [L for L in (found + cl) if passes(L, crit)]
for L in kept:
    print(f"  KEEP {L['price']!s:>6} | {L['title'][:40]}")
# The $4,500 income-restricted one must be dropped (price AND keyword).
assert all(L["price"] != 4500 for L in kept), "income-restricted listing should be filtered"
assert len(kept) == 4, f"expected 4 kept, got {len(kept)}"
print("  OK: over-budget + income-restricted listing filtered out\n")

print("=== Dedupe + feed build ===")
store = {}
new = 0
for L in kept + kept:            # feed the same list twice to prove dedupe
    if L["id"] in store:
        continue
    L["first_seen"] = now().isoformat()
    store[L["id"]] = L
    new += 1
assert new == 4, f"dedupe failed: {new} unique from 8 inputs"
import yaml
cfg = {"feed": {"title": "Test Feed", "link": "https://x.github.io/housing-feed/feed.xml",
                "max_items": 50, "retention_days": 30}}
build_feed(store, cfg)
xml = open("feed.xml").read()
assert "<rss" in xml and "<item>" in xml and xml.count("<item>") == 4
print(f"  OK: 4 unique items -> feed.xml ({len(xml)} bytes), valid RSS\n")
print("ALL TESTS PASSED ✅")
