# Extension authority: AdCP v3.3.0-beta.2, "Check an exact package before booking":
# https://github.com/adcontextprotocol/adcp/blob/v3.3.0-beta.2/docs/media-buy/product-discovery/refinement.mdx#check-an-exact-package-before-booking
# Served version remains 3.1.1; these tests do not claim negotiated AdCP 3.3 support.
# Storyboard: ungraded extension. Stable result_product_id is the branch's limited
# implementation: no changed targeting or configured-product ID binding is tested.
Feature: Check an exact package through product refinement

  @T-package-forecast-exact
  Scenario: Forecast an exact fixed CPM package with insufficient inventory
    Given a package forecast product on the "gam" adapter with a cached forecast
    And GAM reports 120000 matched, 87500 available, and 130000 possible impressions
    When the buyer refines the product at CPM 10 USD with budget 25000 from "2026-11-01T00:00:00Z" to "2026-11-30T23:59:59Z"
    Then the package refinement is position-matched and applied to the same product with the exact flight
    And the package availability forecast reports 87500 impressions as unavailable without a point budget
    And GAM receives the exact UTC flight and a lifetime goal of 2500000 impressions
    And the package check serves version "3.1" without changing the base product or creating a media buy

  @T-package-forecast-vcpm
  Scenario: Forecast an exact fixed vCPM package with insufficient viewable inventory
    Given a fixed vCPM package forecast product on GAM with a cached forecast
    And GAM reports 120000 matched, 87500 available, and 130000 possible impressions
    When the buyer refines the product at vCPM 10 USD with budget 25000 from "2026-11-10T00:00:00Z" to "2026-11-30T23:59:59Z"
    Then the package refinement is position-matched and applied to the same product with the exact flight
    And the package availability forecast reports 87500 impressions as unavailable without a point budget
    And GAM receives a STANDARD vCPM line item with a lifetime goal of 2500000 viewable impressions
    And the package check serves version "3.1" without changing the base product or creating a media buy

  @T-package-forecast-unsupported
  Scenario: Explain an unsupported package forecast without returning cached availability
    Given a package forecast product on the "mock" adapter with a cached forecast
    When the buyer refines the product at CPM 10 USD with budget 25000 from "2026-11-01T00:00:00Z" to "2026-11-30T23:59:59Z"
    Then the package refinement is position-matched and unable with non-empty notes and no product forecast
    And the package check serves version "3.1" without changing the base product or creating a media buy