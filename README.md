# Fuel Price Dashboard

A static dashboard for historical petrol and diesel prices, using source-backed data only.

## Current data coverage

- **United Kingdom:** the workflow fetches the latest official weekly CSV from the [DESNZ weekly road fuel prices page](https://www.gov.uk/government/statistics/weekly-road-fuel-prices), and imports observations from 1 May 2026 onward.
- **EU and USA:** not yet imported. These are not shown as if data were available.
- Missing observations are never fabricated or estimated.
- UK data is weekly, not daily, because that is the publication frequency of this official source.

## Automatic refresh and publishing

The GitHub Actions workflow is scheduled daily at 07:00 UTC and can also be run manually from the Actions tab. It refreshes the UK data and deploys the static page.

For deployment to work, open **Settings → Pages → Build and deployment → Source** and select **GitHub Actions**. Then open the **Actions** tab and check the latest “Refresh fuel prices and deploy dashboard” run. A successful run confirms that data import and deployment completed.

The public site URL should be https://yossarian1979.github.io/FuelPrices/ once the workflow deploys successfully.

## Data schema

The workflow writes observations to `data/prices.json`. Each row includes date, country, region, fuel, source-reported value, unit, and official source URL.

The current chart displays source-reported units. Do not compare countries on a single numerical scale until prices have been converted to a common unit and currency using documented exchange rates.
