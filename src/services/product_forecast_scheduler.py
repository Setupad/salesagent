"""Scheduler for refreshing cached product availability forecasts."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any

from src.core.database.database_session import get_db_session
from src.core.database.repositories import AdapterConfigRepository, CurrencyLimitRepository, ProductRepository

logger = logging.getLogger(__name__)

PRODUCT_FORECAST_REFRESH_INTERVAL_SECONDS = int(os.getenv("PRODUCT_FORECAST_REFRESH_INTERVAL") or "86400")


@dataclass(frozen=True)
class ProductForecastRefreshTarget:
    tenant_id: str
    gam_config: dict[str, Any]
    network_code: str
    currency: str
    product_ids: list[str]


class ProductForecastScheduler:
    """Scheduler for refreshing cached product forecasts."""

    def __init__(self) -> None:
        self.is_running = False
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the scheduler background task."""
        async with self._lock:
            if self.is_running:
                logger.warning("Product forecast scheduler is already running")
                return

            self.is_running = True
            self._task = asyncio.create_task(self._run_scheduler())
            logger.info(
                "Product forecast scheduler started (refreshing every %ss)",
                PRODUCT_FORECAST_REFRESH_INTERVAL_SECONDS,
            )

    async def stop(self) -> None:
        """Stop the scheduler background task."""
        async with self._lock:
            if not self.is_running:
                return

            self.is_running = False
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            logger.info("Product forecast scheduler stopped")

    async def _run_scheduler(self) -> None:
        """Run forecast refreshes on a fixed daily cadence."""
        while self.is_running:
            try:
                await asyncio.to_thread(self._refresh_forecasts)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Error in product forecast scheduler: %s", exc, exc_info=True)
            finally:
                await asyncio.sleep(PRODUCT_FORECAST_REFRESH_INTERVAL_SECONDS)

    def _refresh_forecasts(self) -> None:
        """Refresh cached forecasts for all configured GAM products."""
        logger.info("Starting scheduled product forecast refresh batch")
        targets = self._collect_refresh_targets()
        refreshed_count = 0
        error_count = 0

        from src.adapters.gam.client import GAMClientManager
        from src.services.gam_product_forecast_service import refresh_cached_product_forecast

        for target in targets:
            gam_client_manager = GAMClientManager(target.gam_config, target.network_code)
            for product_id in target.product_ids:
                try:
                    refresh_cached_product_forecast(
                        gam_client_manager,
                        tenant_id=target.tenant_id,
                        product_id=product_id,
                        currency=target.currency,
                    )
                    refreshed_count += 1
                except Exception as exc:
                    logger.error(
                        "Scheduled product forecast refresh failed for %s/%s: %s",
                        target.tenant_id,
                        product_id,
                        exc,
                        exc_info=True,
                    )
                    error_count += 1

        logger.info(
            "Scheduled product forecast refresh batch complete: %s refreshed, %s errors",
            refreshed_count,
            error_count,
        )

    def _collect_refresh_targets(self) -> list[ProductForecastRefreshTarget]:
        with get_db_session() as session:
            adapter_configs = AdapterConfigRepository.list_gam_configs_with_credentials(session)
            targets: list[ProductForecastRefreshTarget] = []

            for adapter_config in adapter_configs:
                network_code = adapter_config.gam_network_code
                if not network_code:
                    continue

                tenant_id = adapter_config.tenant_id
                product_ids = [product.product_id for product in ProductRepository(session, tenant_id).list_all()]
                if not product_ids:
                    continue

                targets.append(
                    ProductForecastRefreshTarget(
                        tenant_id=tenant_id,
                        gam_config=AdapterConfigRepository.get_gam_config(adapter_config),
                        network_code=network_code,
                        currency=CurrencyLimitRepository(session, tenant_id).get_default_currency_code(),
                        product_ids=product_ids,
                    )
                )

            return targets


_scheduler: ProductForecastScheduler | None = None


def get_product_forecast_scheduler() -> ProductForecastScheduler:
    """Get or create the global product forecast scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = ProductForecastScheduler()
    return _scheduler


async def start_product_forecast_scheduler() -> None:
    """Start the product forecast scheduler."""
    scheduler = get_product_forecast_scheduler()
    await scheduler.start()


async def stop_product_forecast_scheduler() -> None:
    """Stop the product forecast scheduler."""
    scheduler = get_product_forecast_scheduler()
    await scheduler.stop()
