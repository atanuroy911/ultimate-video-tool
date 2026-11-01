"""All director APIs see the same module input contract."""
from vt.modules.toolspec import export_module


def test_provider_tools_share_one_json_schema():
    names = ("openai", "anthropic", "gemini", "mcp")
    definitions = [export_module("audio.prosody", name) for name in names]
    schemas = [definition[key] for definition, key in zip(
        definitions, ("parameters", "input_schema", "parametersJsonSchema", "inputSchema"))]
    assert all(schema == schemas[0] for schema in schemas)
    assert schemas[0]["required"] == ["windows"]
    assert all(definition["name"] == "audio.prosody" for definition in definitions)
