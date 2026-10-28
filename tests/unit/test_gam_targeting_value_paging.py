from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.adapters.gam_inventory_discovery import GAMInventoryDiscovery
from src.core.exceptions import AdCPConfigurationError


def gam_values(start: int, count: int) -> list[dict]:
    return [
        {"id": index, "customTargetingKeyId": 42, "name": f"value-{index}"} for index in range(start, start + count)
    ]


def discovery_for_pages(*pages: dict) -> tuple[GAMInventoryDiscovery, Mock]:
    service = Mock()
    service.getCustomTargetingValuesByStatement.side_effect = pages
    client = SimpleNamespace(GetService=Mock(return_value=service))
    discovery = GAMInventoryDiscovery(client=client, tenant_id="paging-test")
    return discovery, service


def test_values_page_continues_beyond_legacy_limit():
    discovery, service = discovery_for_pages({"results": gam_values(1000, 250), "totalResultSetSize": 1500})

    page = discovery.discover_custom_targeting_values_page("42", offset=1000, limit=250)

    assert [value.id for value in page.values] == [str(index) for index in range(1000, 1250)]
    assert page.total_count == 1500
    assert page.next_offset == 1250
    assert page.has_more is True
    statement = service.getCustomTargetingValuesByStatement.call_args.args[0]
    assert "ORDER BY id ASC" in statement["query"]
    assert "LIMIT 250 OFFSET 1000" in statement["query"]
    assert statement["values"] == [{"key": "keyId", "value": {"xsi_type": "NumberValue", "value": 42}}]


@pytest.mark.parametrize("offset,total", [(0, 0), (1500, 1500), (2000, 1500)])
def test_empty_page_has_no_continuation(offset, total):
    discovery, _ = discovery_for_pages({"totalResultSetSize": total})

    page = discovery.discover_custom_targeting_values_page("42", offset=offset, limit=250)

    assert page.values == []
    assert page.total_count == total
    assert page.next_offset is None
    assert page.has_more is False


def test_page_fills_limit_across_gam_responses():
    discovery, service = discovery_for_pages(
        {"results": gam_values(750, 500), "totalResultSetSize": 2000},
        {"results": gam_values(1250, 250), "totalResultSetSize": 2000},
    )

    page = discovery.discover_custom_targeting_values_page("42", offset=750, limit=750)

    assert [value.id for value in page.values] == [str(index) for index in range(750, 1500)]
    assert page.total_count == 2000
    assert page.next_offset == 1500
    assert [call.args[0]["query"] for call in service.getCustomTargetingValuesByStatement.call_args_list] == [
        "WHERE customTargetingKeyId = :keyId ORDER BY id ASC LIMIT 500 OFFSET 750",
        "WHERE customTargetingKeyId = :keyId ORDER BY id ASC LIMIT 250 OFFSET 1250",
    ]


@pytest.mark.parametrize("max_values,expected_count", [(None, 1250), (1000, 1000), (600, 600)])
def test_legacy_list_discovery_preserves_limit_and_cache(max_values, expected_count):
    discovery, _ = discovery_for_pages(
        {"results": gam_values(0, 500), "totalResultSetSize": 1250},
        {"results": gam_values(500, min(500, expected_count - 500)), "totalResultSetSize": 1250},
        {"results": gam_values(1000, 250), "totalResultSetSize": 1250},
    )

    values = discovery.discover_custom_targeting_values_for_key("42", max_values=max_values)

    assert [value.id for value in values] == [str(index) for index in range(expected_count)]
    assert discovery.custom_targeting_values["42"] == values


@pytest.mark.parametrize("offset,limit", [(-1, 250), (0, 0), (0, -1), (0, 1001)])
def test_discovery_rejects_invalid_page_bounds(offset, limit):
    discovery, service = discovery_for_pages()

    with pytest.raises(AdCPConfigurationError):
        discovery.discover_custom_targeting_values_page("42", offset=offset, limit=limit)

    service.getCustomTargetingValuesByStatement.assert_not_called()


@pytest.mark.parametrize(
    "offset,limit,expected",
    [(None, None, (0, 1000)), ("0", "250", (0, 250)), ("1250", None, (1250, 250)), (None, "500", (0, 500))],
)
def test_parse_targeting_values_paging(offset, limit, expected):
    from src.admin.blueprints.inventory import _parse_targeting_values_paging

    assert _parse_targeting_values_paging(offset, limit) == expected


@pytest.mark.parametrize(
    "offset,limit",
    [("-1", "250"), ("0", "0"), ("0", "1001"), ("1.5", "250"), ("0", "bad"), ("", "250"), ("0", "")],
)
def test_parse_targeting_values_paging_rejects_invalid_parameters(offset, limit):
    from src.admin.blueprints.inventory import _parse_targeting_values_paging

    with pytest.raises(ValueError):
        _parse_targeting_values_paging(offset, limit)


def test_final_page_keeps_value_metadata():
    discovery, _ = discovery_for_pages(
        {
            "results": [
                {
                    "id": 1250,
                    "customTargetingKeyId": 42,
                    "name": "sports",
                    "displayName": "Sports",
                    "matchType": "PREFIX",
                    "status": "INACTIVE",
                }
            ],
            "totalResultSetSize": 1251,
        }
    )

    page = discovery.discover_custom_targeting_values_page("42", offset=1250, limit=250)

    assert page.values[0].to_dict() == {
        "id": "1250",
        "custom_targeting_key_id": "42",
        "name": "sports",
        "display_name": "Sports",
        "match_type": "PREFIX",
        "status": "INACTIVE",
    }
    assert page.total_count == 1251
    assert page.next_offset is None
    assert page.has_more is False


@pytest.mark.parametrize(
    "display_name,match_type,status,expected_metadata",
    [
        ("Sports", "PREFIX", "INACTIVE", ("Sports", "PREFIX", "INACTIVE")),
        ("", "", "", ("sports", "EXACT", "ACTIVE")),
    ],
)
def test_format_targeting_values_preserves_metadata_and_defaults(display_name, match_type, status, expected_metadata):
    from src.adapters.gam_inventory_discovery import CustomTargetingValue
    from src.admin.blueprints.inventory import _format_targeting_values

    value = CustomTargetingValue(
        id="1250",
        custom_targeting_key_id="42",
        name="sports",
        display_name=display_name,
        match_type=match_type,
        status=status,
    )

    assert _format_targeting_values([value], "42", "interests") == [
        {
            "id": "1250",
            "name": "sports",
            "display_name": expected_metadata[0],
            "match_type": expected_metadata[1],
            "status": expected_metadata[2],
            "key_id": "42",
            "key_name": "interests",
        }
    ]


def test_format_targeting_values_empty_page():
    from src.admin.blueprints.inventory import _format_targeting_values

    assert _format_targeting_values([], "42", "interests") == []


def test_empty_page_before_total_is_a_failure():
    discovery, _ = discovery_for_pages({"totalResultSetSize": 1500})

    with pytest.raises(AdCPConfigurationError):
        discovery.discover_custom_targeting_values_page("42", offset=250, limit=250)


def test_selectable_template_preserves_json_in_hidden_attribute():
    import json
    from html.parser import HTMLParser
    from pathlib import Path

    from jinja2 import Environment, FileSystemLoader, select_autoescape

    class Inputs(HTMLParser):
        values: dict[str, str | None]

        def __init__(self):
            super().__init__()
            self.values = {}

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            if tag == "input" and attributes.get("name") == "selectable_key_value_pairs":
                self.values = attributes

    templates = Path(__file__).resolve().parents[2] / "templates"
    environment = Environment(loader=FileSystemLoader(templates), autoescape=select_autoescape())
    environment.globals["url_for"] = lambda endpoint, filename: f"/static/{filename}"
    saved = {"hb_env": {"display_name": 'Environment "buyer"', "values": ["amp", "web"]}}
    rendered = environment.get_template("components/selectable_targeting_options.html").render(
        tenant={"ad_server": "gam"},
        tenant_id="test",
        request={"script_root": ""},
        product={"targeting_template": {"selectable_key_value_pairs": saved}},
    )
    parser = Inputs()
    parser.feed(rendered)
    assert json.loads(parser.values["value"]) == saved
