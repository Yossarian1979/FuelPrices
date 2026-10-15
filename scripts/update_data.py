#!/usr/bin/env python3
"""Fetch official UK weekly pump prices and write verified observations."""
import csv
import io
import json
import urllib.request
from datetime import datetime, date, timezone

SOURCE_URL = "https://assets.publishing.service.gov.uk/media/6a9ec4516beb5206555555d2/CSV__2018_-__.csv"
OUT = "data/prices.json"
START = date(2026, 5, 1)

def parse_date(value):
    value = (value or "").strip().lstrip("\ufeff")
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None

req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "FuelPricesDashboard/1.0"})
with urllib.request.urlopen(req, timeout=30) as response:
    raw = response.read().decode("utf-8-sig")
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
    day = parse_date(record.get(date_col))
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
        rows.append({
            "date": day.isoformat(),
            "country": "United Kingdom",
            "region": "uk",
            "fuel": fuel,
            "value": value,
            "unit": "pence/litre",
            "sourceUrl": "https://www.gov.uk/government/statistics/weekly-road-fuel-prices"
        })
if not rows:
    raise RuntimeError("No valid observations found; refusing to overwrite the dataset with an empty file")
rows.sort(key=lambda row: (row["date"], row["fuel"]))
payload = {
    "updatedAt": datetime.now(timezone.utc).date().isoformat(),
    "sourceUpdatedAt": max(row["date"] for row in rows),
    "rows": rows
}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2)
    f.write("\n")
print(f"Wrote {len(rows)} UK observations; latest source date: {payload['sourceUpdatedAt']}")
