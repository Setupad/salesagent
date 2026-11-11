@pricing_option_announcement @requires_db
Feature: Advertiser discounts personalize fixed product prices
  Advertiser discounts are ungraded seller policy.
  The pricing option wire contract remains AdCP 3.1.1.

  Background:
    Given a discount catalog with a 15 percent buyer discount

  @T-advertiser-discount-repeat
  Scenario: Repeated discovery does not compound the fixed price discount
    When the discount buyer discovers the catalog
    Then the discount catalog fixed price is 8.5
    When the discount buyer discovers the catalog
    Then the discount catalog fixed price is 8.5

  @T-advertiser-discount-auction
  Scenario: Fixed price discounts leave auction floors and guidance unchanged
    When the discount buyer discovers the catalog
    Then the discount catalog fixed price is 8.5
    And the discount catalog auction floor is 2 and its median is 5

  @T-advertiser-discount-isolation
  Scenario: A discounted discovery leaves the base price available to another buyer
    When the discount buyer discovers the catalog
    Then the discount catalog fixed price is 8.5
    When the default discount catalog buyer discovers the catalog
    Then the discount catalog fixed price is 10
    When the original discount catalog buyer discovers the catalog
    Then the discount catalog fixed price is 8.5