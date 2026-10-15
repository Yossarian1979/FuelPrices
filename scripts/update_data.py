#!/usr/bin/env python3
"""Import verified UK and EU weekly petrol/diesel prices from published datasets."""
import csv
import gzip
import io
import json
import re
import urllib.request
import zipfile
from datetime import datetime, date, timezone
from html import unescape
from html.parser import HTMLParser

PAGE_URL = "https://www.gov.uk/government/statistics/weekly-road-fuel-prices"
EU_PAGE_URL = "https://www.fuel-prices.eu/research/"
EU_SOURCE_URL = "https://energy.ec.europa.eu/data-and-analysis/weekly-oil-bulletin_en"
OUT = "data/prices.json"
START = date(2026, 5, 1)
HEADERS = {"User-Agent": "FuelPricesDashboard/1.0 (weekly fuel price data)"}


def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read()


def parse_date(value):
    value = (value or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


# UK data: official weekly DESNZ CSV.
page = fetch(PAGE_URL).decode("utf-8", errors="replace")
pattern = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>\s*Weekly road fuel prices \(CSV\) 2018 to 2026\s*</a>', re.I)
match = pattern.search(page)
if not match:
    pattern = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>[^<]*CSV[^<]*2018 to 2026[^<]*</a>', re.I)
    match = pattern.search(page)
if not match:
    raise RuntimeError("Could not locate the current 2018–2026 CSV on GOV.UK")
uk_csv_url = unescape(match.group(1))
if uk_csv_url.startswith("/"):
    uk_csv_url = "https://www.gov.uk" + uk_csv_url
uk_reader = csv.DictReader(io.StringIO(fetch(uk_csv_url).decode("utf-8-sig")))
if not uk_reader.fieldnames:
    raise RuntimeError("UK source CSV has no header row")


def find_column(headers, needle_a, needle_b=None):
    for header in headers:
        h = header.lower()
        if needle_a.lower() in h and (needle_b is None or needle_b.lower() in h):
            return header
    raise RuntimeError(f"Could not identify source column: {needle_a} / {needle_b}")


uk_date_col = find_column(uk_reader.fieldnames, "date")
uk_petrol_col = find_column(uk_reader.fieldnames, "ulsp", "pump price")
uk_diesel_col = find_column(uk_reader.fieldnames, "ulsd", "pump price")
rows = []
for record in uk_reader:
    day = parse_date(record.get(uk_date_col))
    if not day or day < START:
        continue
    for fuel, col in (("petrol", uk_petrol_col), ("diesel", uk_diesel_col)):
        raw_value = (record.get(col) or "").strip().replace(",", "")
        try:
            value = float(raw_value)
        except ValueError:
            continue
        rows.append({"date": day.isoformat(), "country": "United Kingdom", "region": "uk",
                     "fuel": fuel, "value": value, "unit": "pence/litre", "sourceUrl": PAGE_URL})

# EU data: the research dataset is compiled from the European Commission's Weekly Oil Bulletin,
# with values checked against the Commission's historical file. Discover the current CSV link
# from the publisher page rather than hard-coding a versioned filename.
class AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.href = None
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.parts = []

    def handle_data(self, data):
        if self.href is not None:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.href is not None:
            self.links.append((self.href, " ".join(self.parts).strip()))
            self.href = None
            self.parts = []


eu_html = fetch(EU_PAGE_URL).decode("utf-8", errors="replace")
parser = AnchorParser()
parser.feed(eu_html)
candidates = []
for href, label in parser.links:
    text = (href + " " + label).lower()
    if "fp-d1-eu-weekly-panel" in text and (".csv.gz" in text or ".zip" in text):
        candidates.append(href)
    elif "research/data" in href.lower() and ".csv.gz" in href.lower():
        candidates.append(href)
if not candidates:
    raise RuntimeError("Could not find the EU weekly panel CSV link on fuel-prices.eu research page")
eu_csv_url = candidates[0]
if eu_csv_url.startswith("/"):
    eu_csv_url = "https://www.fuel-prices.eu" + eu_csv_url
elif not eu_csv_url.startswith("http"):
    eu_csv_url = "https://www.fuel-prices.eu/" + eu_csv_url.lstrip("/")

eu_raw = fetch(eu_csv_url)
if eu_raw[:2] == b"PK":
    with zipfile.ZipFile(io.BytesIO(eu_raw)) as archive:
        csv_members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not csv_members:
            raise RuntimeError("EU ZIP download contains no CSV file")
        eu_text = archive.read(csv_members[0]).decode("utf-8-sig")
elif eu_raw[:2] == bytes([31, 139]):
    eu_text = gzip.decompress(eu_raw).decode("utf-8-sig")
else:
    eu_text = eu_raw.decode("utf-8-sig", errors="replace")
eu_reader = csv.DictReader(line for line in io.StringIO(eu_text) if not line.startswith("#"))
required = {"country_name", "week", "in_eu", "euro95_eur_l", "diesel_eur_l"}
if not eu_reader.fieldnames or not required.issubset(set(eu_reader.fieldnames)):
    raise RuntimeError(f"Unexpected EU CSV schema; got headers: {eu_reader.fieldnames}")
eu_count = 0
for record in eu_reader:
    if (record.get("in_eu") or "").strip().lower() not in ("true", "1", "yes"):
        continue
    day = parse_date(record.get("week"))
    if not day or day < START:
        continue
    for fuel, col in (("petrol", "euro95_eur_l"), ("diesel", "diesel_eur_l")):
        raw_value = (record.get(col) or "").strip()
        try:
            value = float(raw_value)
        except ValueError:
            continue
        rows.append({"date": day.isoformat(), "country": record["country_name"].strip(), "region": "eu",
                     "fuel": fuel, "value": value, "unit": "EUR/litre",
                     "sourceUrl": EU_SOURCE_URL,
                     "dataAttribution": "European Commission Weekly Oil Bulletin; compiled by fuel-prices.eu (CC BY 4.0)"})
        eu_count += 1

if not rows:
    raise RuntimeError("No valid observations found; refusing to overwrite the dataset with an empty file")
rows.sort(key=lambda row: (row["date"], row["country"], row["fuel"]))
eu_dates = [r["date"] for r in rows if r["region"] == "eu"]
uk_dates = [r["date"] for r in rows if r["region"] == "uk"]
payload = {
    "updatedAt": datetime.now(timezone.utc).date().isoformat(),
    "sourceUpdatedAt": max(eu_dates) if eu_dates else max(uk_dates),
    "sourceUrl": PAGE_URL,
    "sources": {"uk": PAGE_URL, "eu": EU_SOURCE_URL, "euDataset": EU_PAGE_URL},
    "rows": rows
}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2)
    f.write("\n")
print(f"Wrote {len(uk_dates)} UK and {eu_count} EU observations; latest EU date: {max(eu_dates) if eu_dates else 'none'}; EU CSV: {eu_csv_url}")
