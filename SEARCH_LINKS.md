# 🔗 Your saved-search links — Portland, OR (97212 / 97214 / 97232 / 97215)

Your spec, applied everywhere below:
**2+ bed · 1+ bath · $1,000–$2,000 · 1,000+ sqft · houses/townhomes/duplexes (no big complexes) · cat-friendly · older building preferred.**

> On each site: open the link → confirm the filters → click **Save Search** → turn on **email alerts** → point them at your dedicated housing Gmail. (Most sites need a free account to save a search + get emails.) All alerts then flow into the aggregator automatically.

---

## 1. Craigslist — fully pre-filtered ✅ (just log in and save)

This URL already encodes every filter, including "house / townhouse / duplex / flat / cottage / in-law" and **excludes apartment & condo building types** — exactly your "no large apartment buildings" rule:

```
https://portland.craigslist.org/search/apa?min_price=1000&max_price=2000&min_bedrooms=2&min_bathrooms=1&minSqft=1000&pets_cat=1&housing_type=3&housing_type=4&housing_type=5&housing_type=6&housing_type=7&housing_type=9&postal=97214&search_distance=3
```

Then: **account → Searches tab → tick Alert ✅.** (`search_distance=3` miles from 97214 covers all four ZIPs; widen/narrow to taste.)

---

## 2. Zillow — 4 saved searches (one per ZIP)

Open each, then set filters in the UI: **For Rent · Beds 2+ · Price $1,000–$2,000 · Home Type = Houses + Townhomes (uncheck Apartments/Condos) · More → Square Feet min 1,000 · Pets = Cats**, then **Save search → Email**.

- https://www.zillow.com/homes/for_rent/97212_rb/
- https://www.zillow.com/homes/for_rent/97214_rb/
- https://www.zillow.com/homes/for_rent/97232_rb/
- https://www.zillow.com/homes/for_rent/97215_rb/

(Four alert emails is fine — the aggregator de-dupes across all of them.)

---

## 3. Apartments.com — houses category, pre-filtered

```
https://www.apartments.com/houses/portland-or/2-bedrooms-under-2000-pet-friendly-cat/
```

Confirm min price $1,000 and 1,000+ sqft in the filter bar, then **Save Search → email = Immediately**. The `/houses/` path already keeps you out of large apartment communities.

---

## 4. Zumper — houses, 2-bed

```
https://www.zumper.com/houses-for-rent/portland-or-2-bedroom
```

Set **max price $2,000 · cats OK · 1,000+ sqft**, then **Save search → email alerts on**.

---

## 5. HotPads — houses

```
https://hotpads.com/portland-or/houses-for-rent?beds=2
```

Set **price 1000–2000 · sqft 1000+ · pets: cats**, then **Save Search → alerts on**.

---

## 6. Local property managers (inner NE/SE specialists)

These manage exactly the older single-family homes, duplexes, and plexes you want in your ZIPs. Most **syndicate their listings to Zillow/Craigslist**, so the aggregator already catches them — but set an on-site alert where offered, and bookmark the rest for a weekly manual glance:

| Company | Rentals page | Notes |
|---|---|---|
| Rent Portland Homes | rentportlandhomes.com | Explicitly serves Irvington/NE/SE; houses & plexes |
| Portland Property Management | portlandpm.com | Single-family, condos, plexes across NE/SE/Hawthorne |
| Performance Properties Inc. | ppirentals.com | Residential, 40+ yrs, small buildings |
| Portland Rental Properties | portlandrentalproperties.com | Single-family + small/mid plexes |
| Sleep Sound Property Mgmt | propertymanagementportlandor.com | Searchable rental homes |

> Want me to check which of these have an email-alert / "notify me" option and wire those into the same inbox? Say the word and I'll go through them.

---

## Notes on your "older building" preference

No rental site has a clean "built before year X" filter. We enforce it three ways: (1) restricting to **houses/townhomes/duplexes** (which in these historic streetcar neighborhoods are overwhelmingly old housing stock), (2) **exclude-keywords** in `config.yaml` that drop "new construction / newly built / resort-style / fitness center / clubhouse", and (3) your own quick glance at the feed. Tell me if you want me to also **exclude specific new-build complexes** by name.
