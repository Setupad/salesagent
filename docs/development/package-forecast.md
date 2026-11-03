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

An authenticated buyer can check fixed CPM packages on Google Ad Manager.
The package requires `pricing_option_id` and `budget`; optional `impressions`
overrides the goal derived from budget and CPM. Supply timezone-aware flight
timestamps. Date-only filter fallbacks use UTC day boundaries.

The forecast uses the product's inventory and creative placeholders. Country
inclusions and exclusions are supported. Other overlays, unresolved product
targeting defaults, unsupported adapters, auction prices, and free-text asks
return `unable` with notes. They never substitute a cached forecast.

Every entry has a position-matched `refinement_applied` outcome. Successful
package checks include `result_product_id` and the resolved flight. Forecast
points report total available impressions and `availability_status`; insufficient
inventory is an applied check with `unavailable`, rather than an inability to
forecast. Point budgets are omitted.

Each check is independent. It creates no media buy, reserves no inventory, and
does not change the stored product. The base product ID is retained: this local
extension does not implement 3.3 configured-product IDs or bind package settings
to a later purchase. Send the same structured settings when creating the buy;
availability can change before booking. Strict 3.1-only clients must opt in to
the additional response fields to consume this extension.