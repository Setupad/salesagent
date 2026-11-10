# GAM forecast targeting

## Contract grounding

This conversion targets AdCP 3.1.1, pinned through `adcp==6.6.0`.
The authoritative [targeting specification, Frequency capping section](https://github.com/adcontextprotocol/adcp/blob/v3.1.1/docs/media-buy/advanced-topics/targeting.mdx#frequency-capping)
defines cooldown and impression-count controls as independent constraints.
The [frequency-cap schema](https://github.com/adcontextprotocol/adcp/blob/v3.1.1/dist/schemas/3.1.1/core/frequency-cap.json)
requires `per` and `window` with `max_impressions` and specifies AND semantics.
The [daypart schema](https://github.com/adcontextprotocol/adcp/blob/v3.1.1/dist/schemas/3.1.1/core/daypart-target.json)
defines inclusive start hours, exclusive end hours, and an end after the start.

The [frequency enforcement storyboard](https://github.com/adcontextprotocol/adcp/blob/v3.1.1/dist/compliance/3.1.1/domains/media-buy/scenarios/frequency_cap_enforcement.yaml)
grades `create_media_buy_with_frequency_cap` and observed delivery frequency.
GAM package forecast conversion and daypart forecasting are **ungraded**.
These pure conversion tests do not claim runtime frequency enforcement coverage.

## Discovery and capability metadata

The AdCP 3.1.1 [buyer brief guide](https://github.com/adcontextprotocol/adcp/blob/v3.1.1/docs/learning/supplements/buyer-briefs-and-get-products.mdx#mental-model)
puts buyer intent in `brief` and machine-enforceable constraints in typed fields.
The [refinement storyboard](https://github.com/adcontextprotocol/adcp/blob/v3.1.1/dist/compliance/3.1.1/domains/media-buy/scenarios/refine_products.yaml)
grades product refinement and `refinement_applied`; exact package forecasting is
a seller extension and remains ungraded. For exact geo, frequency, and daypart
forecasts, call `get_products` with `buying_mode: "refine"`, a product refinement,
and `package.targeting_overlay`. A discovery brief is not proof of applied targeting.
The registry owns the MCP tool description, and the request DTO owns field metadata.

The pinned [capability response schema](https://github.com/adcontextprotocol/adcp/blob/v3.1.1/dist/schemas/3.1.1/protocol/get-adcp-capabilities-response.json)
defines geographic targeting declarations but no frequency, daypart, or exact-forecast
flags. Its [media-buy features schema](https://github.com/adcontextprotocol/adcp/blob/v3.1.1/dist/schemas/3.1.1/core/media-buy-features.json)
also defines none of those flags. Keep capability declarations in that vocabulary;
tool and field descriptions explain the forecast extension instead.

The frequency-cap schema specifies package-level application and declares no `scope`.
The local scope extension remains for Kevel compatibility and defaults to `package`.
GAM rejects an explicit `media_buy` scope in creation and forecasting because its
line-item caps cannot enforce a shared cap across packages.

## GAM representation

GAM [ForecastService LineItem](https://developers.google.com/ad-manager/api/reference/v202511/ForecastService.LineItem#frequencyCaps)
accepts top-level `frequencyCaps`. Its [FrequencyCap](https://developers.google.com/ad-manager/api/reference/v202511/ForecastService.FrequencyCap)
uses integer `maxImpressions`, `numTimeUnits`, and `timeUnit` for a single viewer.
GAM identifies viewers through cookies or device identifiers; this conversion
supports `cookies` and `devices`, without promising household or individual identity.
Other entity types and undeclared scopes require explicit rejection.

Cooldowns map to one impression per exact interval. Seconds require an integral
minute equivalent. Fractional minutes are rejected rather than rounded.
Dayparts use the shared converter, merge overlapping windows, and set
`targeting.dayPartTargeting.timeZone` to `PUBLISHER`.

Google's [frequency capping and forecasting limitations](https://support.google.com/admanager/answer/82242)
state that monthly and lifetime caps can overpredict. Exact forecasts reject those
product caps and campaign windows, along with video pod and stream windows.
Creation and forecasting share frequency conversion; creation retains its product
monthly and lifetime caps. Neither path invents cross-package or cross-buy scope.

GAM rejects duplicate time units and duplicate time ranges, as documented in
[FrequencyCapError](https://developers.google.com/ad-manager/api/reference/v202511/ForecastService.FrequencyCapError).
The converter merges equal ranges using the lower impression limit and rejects
distinct ranges with the same chosen unit. It rejects more than ten merged caps.
The forecast represents GAM's viewer-identifier behavior; it does not guarantee
cross-device identity, identifier availability, or exact delivery outcomes.