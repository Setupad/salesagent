from unittest.mock import MagicMock, patch

from src.services.product_forecast_scheduler import ProductForecastScheduler


class FakeSessionContext:
    def __init__(self, session: MagicMock) -> None:
        self.session = session

    def __enter__(self) -> MagicMock:
        return self.session

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


def test_product_forecast_scheduler_refreshes_all_gam_products() -> None:
    session = MagicMock()
    adapter_config = MagicMock()
    adapter_config.tenant_id = "tenant_a"
    adapter_config.gam_network_code = "12345"
    gam_config = {"auth": "ok"}
    product_a = MagicMock(product_id="prod_a")
    product_b = MagicMock(product_id="prod_b")

    with (
        patch("src.services.product_forecast_scheduler.get_db_session", return_value=FakeSessionContext(session)),
        patch(
            "src.services.product_forecast_scheduler.AdapterConfigRepository.list_gam_configs_with_credentials",
            return_value=[adapter_config],
        ),
        patch("src.services.product_forecast_scheduler.AdapterConfigRepository.get_gam_config", return_value=gam_config),
        patch("src.services.product_forecast_scheduler.CurrencyLimitRepository") as currency_repo_class,
        patch("src.services.product_forecast_scheduler.ProductRepository") as product_repo_class,
        patch("src.adapters.gam.client.GAMClientManager") as gam_client_manager_class,
        patch("src.services.gam_product_forecast_service.refresh_cached_product_forecast") as refresh_forecast,
    ):
        currency_repo_class.return_value.get_default_currency_code.return_value = "EUR"
        product_repo_class.return_value.list_all.return_value = [product_a, product_b]
        gam_client_manager = gam_client_manager_class.return_value

        ProductForecastScheduler()._refresh_forecasts()

    gam_client_manager_class.assert_called_once_with(gam_config, "12345")
    refresh_forecast.assert_any_call(
        gam_client_manager,
        tenant_id="tenant_a",
        product_id="prod_a",
        currency="EUR",
    )
    refresh_forecast.assert_any_call(
        gam_client_manager,
        tenant_id="tenant_a",
        product_id="prod_b",
        currency="EUR",
    )
    assert refresh_forecast.call_count == 2
