import logging

from src.core.creative_agent_registry import CreativeAgentRegistry


def test_prefers_structured_content_formats():
    result = {
        "content": [{"type": "text", "text": "list_creative_formats completed successfully."}],
        "structuredContent": {
            "formats": [
                {
                    "format_id": {"agent_url": "https://creative.example.com", "id": "display_image"},
                    "name": "Display Image",
                    "type": "display",
                }
            ]
        },
    }

    formats = CreativeAgentRegistry()._parse_mcp_tool_result(result, logging.getLogger(__name__))

    assert len(formats) == 1
    assert formats[0].format_id.id == "display_image"


def test_structured_content_tolerates_additive_format_parameters():
    result = {
        "structuredContent": {
            "formats": [
                {
                    "format_id": {"agent_url": "https://creative.example.com", "id": "display_image"},
                    "name": "Display Image",
                    "type": "display",
                    "accepts_parameters": ["dimensions", "pixel_ratio"],
                }
            ]
        }
    }

    formats = CreativeAgentRegistry()._parse_mcp_tool_result(result, logging.getLogger(__name__))

    assert len(formats) == 1
    assert formats[0].format_id.id == "display_image"
    assert [parameter.value for parameter in formats[0].accepts_parameters or []] == ["dimensions"]