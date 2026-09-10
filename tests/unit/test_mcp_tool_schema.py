"""MCP tool schema regression tests."""


def test_sync_creatives_advertises_top_level_assignments():
    """sync_creatives must expose request-level assignments to MCP clients."""
    from src.core import main

    tool = main.mcp._local_provider._components["tool:sync_creatives@"]
    properties = tool.parameters.get("properties", {})

    assert "creatives" in properties
    assert "assignments" in properties
