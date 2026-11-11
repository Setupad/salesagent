from decimal import Decimal

import pytest

from tests.factories import PrincipalFactory, TenantFactory
from tests.helpers.admin_session import admin_auth_session

pytestmark = [pytest.mark.admin, pytest.mark.requires_db]


@pytest.fixture
def advertiser(admin_client, factory_session):
    tenant = TenantFactory()
    principal = PrincipalFactory(tenant=tenant, discount_percentage=Decimal("4.25"))
    admin_auth_session(admin_client, tenant.tenant_id)
    return principal


def discount_url(principal):
    return f"/tenant/{principal.tenant_id}/principal/{principal.principal_id}/discount"


@pytest.mark.parametrize("value,expected", [("12.50", "12.50"), (0, "0.00"), (99.99, "99.99")])
def test_updates_only_discount(admin_client, factory_session, advertiser, value, expected):
    original_name = advertiser.name
    original_mappings = advertiser.platform_mappings
    response = admin_client.post(discount_url(advertiser), json={"discount_percentage": value})

    assert response.status_code == 200
    assert response.get_json() == {"success": True, "discount_percentage": expected}
    factory_session.refresh(advertiser)
    assert advertiser.discount_percentage == Decimal(expected)
    assert advertiser.name == original_name
    assert advertiser.platform_mappings == original_mappings


@pytest.mark.parametrize(
    "payload",
    [
        {},
        [],
        [1],
        True,
        "invalid",
        {"discount_percentage": True},
        {"discount_percentage": None},
        {"discount_percentage": {}},
        {"discount_percentage": []},
        {"discount_percentage": ""},
        {"discount_percentage": "NaN"},
        {"discount_percentage": "Infinity"},
        {"discount_percentage": "-0.01"},
        {"discount_percentage": "100"},
        {"discount_percentage": "1.001"},
        {"discount_percentage": "5", "name": "Changed"},
    ],
)
def test_rejects_invalid_json_values(admin_client, factory_session, advertiser, payload):
    response = admin_client.post(discount_url(advertiser), json=payload)

    assert response.status_code == 400
    assert isinstance(response.get_json()["error"], str)
    factory_session.refresh(advertiser)
    assert advertiser.discount_percentage == Decimal("4.25")


@pytest.mark.parametrize(
    "options",
    [
        {"data": {"discount_percentage": "10"}},
        {"data": '{"discount_percentage":', "content_type": "application/json"},
    ],
)
def test_rejects_form_and_malformed_json(admin_client, advertiser, options):
    response = admin_client.post(discount_url(advertiser), **options)

    assert response.status_code == 400
    assert isinstance(response.get_json()["error"], str)


def test_missing_advertiser_returns_404(admin_client, advertiser):
    response = admin_client.post(
        f"/tenant/{advertiser.tenant_id}/principal/missing/discount", json={"discount_percentage": "10"}
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "Principal not found"}


def test_cannot_update_another_tenants_advertiser(admin_client, factory_session, advertiser):
    other_tenant = TenantFactory()
    response = admin_client.post(
        f"/tenant/{other_tenant.tenant_id}/principal/{advertiser.principal_id}/discount",
        json={"discount_percentage": "10"},
    )

    assert response.status_code == 404
    factory_session.refresh(advertiser)
    assert advertiser.discount_percentage == Decimal("4.25")


def test_unauthenticated_request_cannot_update_discount(admin_client, factory_session, advertiser):
    with admin_client.session_transaction() as admin_session:
        admin_session.clear()
    response = admin_client.post(discount_url(advertiser), json={"discount_percentage": "10"})

    assert response.status_code in {302, 401}
    factory_session.refresh(advertiser)
    assert advertiser.discount_percentage == Decimal("4.25")
