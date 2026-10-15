#!/usr/bin/env python3
"""Fetch the latest official UK weekly pump-price CSV and write verified observations."""
import csv
import io
import json
import re
import urllib.request
from datetime import datetime, date, timezone
from html import unescape

PAGE_URL = "https://www.gov.uk/government/statistics/weekly-road-fuel-prices"
OUT = "data/prices.json"
START = date(2026, 5, 1)
HEADERS = {"User-Agent": "FuelPricesDashboard/1.0"}

def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()

page = fetch(PAGE_URL).decode("utf-8", errors="replace")
pattern = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>\s*Weekly road fuel prices \(CSV\) 2018 to 2026\s*</a>', re.I)
match = pattern.search(page)
if not match:
    pattern = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>[^<]*CSV[^<]*2018 to 2026[^<]*</a>', re.I)
    match = pattern.search(page)
if not match:
    raise RuntimeError("Could not locate the current 2018–2026 CSV link on the official GOV.UK page")
csv_url = unescape(match.group(1))
if csv_url.startswith("/"):
    csv_url = "https://www.gov.uk" + csv_url
raw = fetch(csv_url).decode("utf-8-sig")
reader = csv.DictReader(io.StringIO(raw))
if not reader.fieldnames:
    raise RuntimeError("Source CSV has no header row")

def find_column(needle_a, needle_b=None):
    for header in reader.fieldnames:
        h = header.lower()
        if needle_a.lower() in h and (needle_b is None or needle_b.lower() in h):
            return header
    raise RuntimeError(f"Could not identify source column: {needle_a} / {needle_b}")

date_col = find_column("date")
petrol_col = find_column("ulsp", "pump price")
diesel_col = find_column("ulsd", "pump price")
rows = []
for record in reader:
    raw_date = (record.get(date_col) or "").strip()
    day = None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            day = datetime.strptime(raw_date, fmt).date()
            break
        except ValueError:
            continue
    if not day or day < START:
        continue
    for fuel, col in (("petrol", petrol_col), ("diesel", diesel_col)):
        raw_value = (record.get(col) or "").strip().replace(",", "")
        if not raw_value:
            continue
        try:
            value = float(raw_value)
        except ValueError:
            continue
        rows.append({"date": day.isoformat(), "country": "United Kingdom", "region": "uk",
                     "fuel": fuel, "value": value, "unit": "pence/litre", "sourceUrl": PAGE_URL})
if not rows:
    raise RuntimeError("No valid observations found; refusing to overwrite the dataset with an empty file")
rows.sort(key=lambda row: (row["date"], row["fuel"]))
payload = {"updatedAt": datetime.now(timezone.utc).date().isoformat(),
           "sourceUpdatedAt": max(row["date"] for row in rows), "sourceUrl": PAGE_URL, "rows": rows}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2)
    f.write("\n")
print(f"Wrote {len(rows)} UK observations; latest source date: {payload['sourceUpdatedAt']}; CSV: {csv_url}")
