#!/usr/bin/env python3
"""Fetch UK weekly fuel prices from the official GOV.UK CSV; never synthesise values."""
import csv
import io
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "prices.json"
PAGE = "https://www.gov.uk/government/statistics/weekly-road-fuel-prices"
HEADERS = {"User-Agent": "FuelPriceDashboard/1.0 (public data tracker)"}

def main():
    page = requests.get(PAGE, headers=HEADERS, timeout=30)
    page.raise_for_status()
    soup = BeautifulSoup(page.text, "html.parser")
    csv_url = None
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = " ".join(a.get_text(" ", strip=True).split()).lower()
        if "csv" in text and "2018 to 2026" in text and ".csv" in href.lower():
            csv_url = urljoin(PAGE, href)
            break
    if not csv_url:
        # Fallback: use the CSV attachment link if the GOV.UK page labels it differently.
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if "/csv-preview/" in href and href.lower().endswith(".csv"):
                csv_url = urljoin(PAGE, href)
                break
    if not csv_url:
        raise RuntimeError("Could not find the official UK historical CSV link on GOV.UK; leaving existing dataset untouched.")

    response = requests.get(csv_url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    content = response.content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise RuntimeError("Official UK CSV has no header; leaving existing dataset untouched.")

    def find_col(words):
        for col in reader.fieldnames:
            low = col.lower()
            if all(word in low for word in words):
                return col
        return None

    date_col = next((c for c in reader.fieldnames if c.strip().lower() == "date"), None)
    petrol_col = next((c for c in reader.fieldnames if "ulsp" in c.lower() and "pump price" in c.lower()), None)
    diesel_col = next((c for c in reader.fieldnames if "ulsd" in c.lower() and "pump price" in c.lower()), None)
    if not date_col or not petrol_col or not diesel_col:
        raise RuntimeError("Unexpected GOV.UK CSV columns: " + repr(reader.fieldnames) + "; leaving existing dataset untouched.")

    rows = []
    for row in reader:
        try:
            date = datetime.strptime(row[date_col].strip(), "%d/%m/%Y").date().isoformat()
        except (ValueError, AttributeError):
            continue
        if date < "2026-05-01":
            continue
        for fuel, col in (("petrol", petrol_col), ("diesel", diesel_col)):
            raw = (row.get(col) or "").strip().replace(",", "")
            try:
                value = float(raw)
            except ValueError:
                continue
            rows.append({
                "date": date, "country": "United Kingdom", "region": "uk",
                "fuel": fuel, "value": value, "unit": "pence/litre",
                "sourceUrl": csv_url
            })
    if not rows:
        raise RuntimeError("No UK observations from 1 May 2026 onward found; refusing to overwrite dataset with empty data.")

    # Preserve any other sourced rows already present, then replace the UK series with latest source contents.
    existing = {"rows": []}
    if OUT.exists():
        try:
            existing = json.loads(OUT.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {"rows": []}
    other = [r for r in existing.get("rows", []) if r.get("region") != "uk"]
    combined = other + rows
    combined.sort(key=lambda r: (r["date"], r["country"], r["fuel"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"updatedAt": datetime.utcnow().date().isoformat(), "rows": combined}, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(rows)} official UK observations from {min(r['date'] for r in rows)} to {max(r['date'] for r in rows)}.")
    print("EU and US series are not yet imported; they remain absent rather than estimated.")

if __name__ == "__main__":
    main()
