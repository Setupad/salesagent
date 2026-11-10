import ast
from pathlib import Path

from adcp.types.generated_poc.core.media_buy_features import MediaBuyFeatures
from adcp.types.generated_poc.protocol.get_adcp_capabilities_response import Targeting

from src.core.schemas.product import GetProductsRequest


def test_forecast_schema_distinguishes_discovery_from_exact_targeting() -> None:
    schema = GetProductsRequest.model_json_schema()
    brief = schema["properties"]["brief"]["description"]
    assert "discovery" in brief.lower()
    assert "not proof" in brief
    overlay = schema["$defs"]["PackageForecastInput"]["properties"]["targeting_overlay"]["description"]
    for dimension in ("geo", "frequency", "daypart"):
        assert dimension in overlay
    refine = schema["properties"]["refine"]["description"]
    assert "buying_mode" in refine
    assert "package.targeting_overlay" in refine


def test_mcp_uses_registry_owned_forecast_description() -> None:
    root = Path(__file__).resolve().parents[2]
    registry = ast.parse((root / "src/core/tools/registry.py").read_text())
    rows = next(
        node
        for node in ast.walk(registry)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "_TOOLS"
    )
    products = next(
        value for key, value in zip(rows.value.keys, rows.value.values, strict=True) if key.value == "get_products"
    )
    description = next(keyword.value.value for keyword in products.keywords if keyword.arg == "description")
    for term in ("buying_mode", "refine", "package.targeting_overlay", "brief", "not proof"):
        assert term in description
    main = ast.parse((root / "src/core/main.py").read_text())
    description_values = [
        keyword.value
        for node in ast.walk(main)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "RegistryTool"
        for keyword in node.keywords
        if keyword.arg == "description"
    ]
    assert any(
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "spec"
        and node.attr == "description"
        for value in description_values
        for node in ast.walk(value)
    )


def test_capability_builder_uses_only_pinned_targeting_and_feature_fields() -> None:
    root = Path(__file__).resolve().parents[2]
    tree = ast.parse((root / "src/services/seller_capabilities.py").read_text())
    models = {"Targeting": Targeting, "MediaBuyFeatures": MediaBuyFeatures}
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in models
    ]
    assert {node.func.id for node in calls} == set(models)
    for call in calls:
        declared = {keyword.arg for keyword in call.keywords}
        assert declared <= set(models[call.func.id].model_fields)
        assert not declared.intersection({"frequency_cap", "daypart_targets", "exact_forecast"})
