@requires_db
Feature: Advertiser discounts apply to new orders and preserve saved terms
  Discounts and saved effective rates are ungraded seller policy.
  AdCP 3.1.1 media-buy/create-media-buy-request.json defines replay by key and account.

  Background:
    Given an order catalog with fixed rates 10 and 20 and a 15 percent buyer discount

  @T-advertiser-discount-order-rates
  Scenario: Fixed option selection saves discounted rates without reducing budgets
    When the discount buyer submits order "initial"
    Then the order saves rates 8.5 and 17 with budgets 1000 and 500
    And the order adapter receives the saved rates and unchanged budgets

  @T-advertiser-discount-order-history
  Scenario: A discount change affects a new order and preserves previous terms
    When the discount buyer submits order "previous"
    Then the order saves rates 8.5 and 17 with budgets 1000 and 500
    And the buyer remembers the order response and saved package terms
    When the order buyer discount changes to 25 percent
    And the discount buyer submits order "following"
    Then the order saves rates 7.5 and 15 with budgets 1000 and 500
    And the previous order retains its saved package terms

  @T-advertiser-discount-order-replay
  Scenario: Replaying an order after a discount change preserves the original response
    When the discount buyer submits order "replayed"
    Then the order saves rates 8.5 and 17 with budgets 1000 and 500
    And the buyer remembers the order response and saved package terms
    When the order buyer discount changes to 25 percent
    And the discount buyer submits order "replayed"
    Then the replay returns the remembered response and saved package terms