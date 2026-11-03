"""Bind exact-package refinement scenarios to the real product discovery path."""

from collections.abc import Iterator

import pytest
from pytest_bdd import scenarios

from tests.bdd.steps.package_forecast_refine import *  # noqa: F401,F403
from tests.bdd.steps.package_forecast_refine import PackageForecastEnv

pytestmark = pytest.mark.requires_db

scenarios("features/package-forecast-refine.feature")


@pytest.fixture(autouse=True)
def _harness_env(ctx: dict, integration_db: object) -> Iterator[None]:
    with PackageForecastEnv() as env:
        ctx["env"] = env
        yield
