# Package availability forecasts

The seller keeps AdCP 3.1.1 and SDK 6.6.0. It exposes a local extension to
`get_products`: product-scoped `refine` entries accept `package`, based on
[AdCP 3.3.0-beta.2 package refinement](https://github.com/adcontextprotocol/adcp/blob/v3.3.0-beta.2/docs/media-buy/product-discovery/refinement.mdx#check-an-exact-package-before-booking).
The field is included in the generated tool schema. This extension is ungraded
by the pinned conformance storyboards and does not announce AdCP 3.3 support.

```json
{
  "buying_mode": "refine",
  "refine": [{
    "scope": "product",
    "product_id": "your-product-id",
    "package": {
      "pricing_option_id": "your-pricing-option-id",
      "budget": 25000,
      "start_time": "2026-11-01T00:00:00Z",
      "end_time": "2026-11-30T23:59:59Z",
      "targeting_overlay": {"geo_countries": ["LT"]}
    }
  }]
}
```

An authenticated buyer can check fixed CPM and vCPM packages on Google Ad Manager.
The package requires `pricing_option_id` and `budget`; optional `impressions`
overrides the goal derived from budget and the fixed price. For vCPM, this goal
counts viewable impressions. Supply timezone-aware flight timestamps. Date-only
filter fallbacks use UTC day boundaries.

The forecast uses the product's inventory and creative placeholders. Country
inclusions and exclusions and buyer-selectable GAM key/value overlays are
supported, including Cxense segments declared by the product. Other overlays, unresolved product
targeting defaults, unsupported adapters, auction prices, and free-text asks
return `unable` with notes. They never substitute a cached forecast.

Custom targeting uses `targeting_overlay.custom.gam.key_value_pairs` (or its
`key_values` alias, one at a time). Keys and values must match the product's
`ext.prebid.selectable_key_value_pairs`; send the stored value, not its display
label. The forecast looks up existing GAM value IDs without creating values.
A missing value returns `unable` rather than an untargeted forecast.

For example, if the product declares `CxSegments` with the stored value
`female`, a combined overlay is:

```json
{
  "geo_countries": ["LV"],
  "custom": {"gam": {"key_value_pairs": {"CxSegments": ["female"]}}}
}
```

Country mappings load from `src/adapters/gam_geo_mappings.json`. The manager's
path follows its location under `gam/managers`; the old path left every country
unmapped after that module moved. Latvia, Lithuania, and Estonia are included,
with IDs verified against the
[Google geo target CSV](https://developers.google.com/ad-manager/api/geotargets).

Every entry has a position-matched `refinement_applied` outcome. Successful
package checks include `result_product_id` and the resolved flight. Forecast
points report total available impressions and `availability_status`; insufficient
inventory is an applied check with `unavailable`, rather than an inability to
forecast. Point budgets are omitted.

vCPM checks use GAM `STANDARD` line items, `VCPM` cost type, and
`VIEWABLE_IMPRESSIONS` lifetime goals, including for non-guaranteed products.
The pinned forecast model has no separate viewable-impressions metric, so vCPM
availability remains in `metrics.impressions` and is identified by
`forecast.ext.gam_unit_type: "VIEWABLE_IMPRESSIONS"`. These units follow the
[GAM forecast goal unit](https://developers.google.com/ad-manager/api/reference/v202602/ForecastService.AvailabilityForecast).

Each check is independent. It creates no media buy, reserves no inventory, and
does not change the stored product. The base product ID is retained: this local
extension does not implement 3.3 configured-product IDs or bind package settings
to a later purchase. Send the same structured settings when creating the buy;
availability can change before booking. Strict 3.1-only clients must opt in to
the additional response fields to consume this extension.