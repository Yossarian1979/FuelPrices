# Fuel Price Dashboard

Static dashboard for verified petrol and diesel observations across the UK, EU and USA.

## Current status

- `index.html` contains the dashboard.
- `data/prices.json` is currently empty by design. No prices have been fabricated.
- Data source links are included in the page; source links alone do not mean the data has been imported.
- Automatic daily refresh is **not configured yet**.

## Publish with GitHub Pages

1. Make this repository public if you want a public website (Settings → General → Danger Zone → Change repository visibility). Do not make it public if you intend to keep the code private.
2. Open Settings → Pages.
3. Under Build and deployment, select **Deploy from a branch**.
4. Select branch `main` and folder `/ (root)`, then Save.
5. After GitHub finishes deploying, the expected URL is https://yossarian1979.github.io/FuelPrices/ .

## Data format

Add verified observations to `data/prices.json` using this structure:

```json
{
  "updatedAt": "YYYY-MM-DD",
  "rows": [
    {
      "date": "YYYY-MM-DD",
      "country": "United Kingdom",
      "region": "uk",
      "fuel": "petrol",
      "value": 0,
      "unit": "pence/litre",
      "sourceUrl": "https://official-source.example/data"
    }
  ]
}
```

Use only source-backed values. Do not mix units or currencies on the same chart unless they have been normalised with a documented conversion. This dashboard currently displays the source-reported values and labels this limitation.
