import json

from dashboard_engine.generator import DashboardGenerator


def test_build_full_config_adds_generation_date():
    config = {"title": "Test", "widgets": []}

    full = DashboardGenerator._build_full_config(config)

    # Keep original keys intact
    assert full["title"] == "Test"
    assert full["widgets"] == []

    # Enriched metadata
    assert "generation_date" in full
    assert isinstance(full["generation_date"], str)
    assert len(full["generation_date"]) == 8  # YYYYMMDD


def test_build_context_structure_is_stable():
    config = {"title": "My Dashboard", "subtitle": "Sub", "dev_mode": True}
    full_config = {"foo": "bar"}

    context = DashboardGenerator._build_context(
        config=config,
        full_config=full_config,
        datasets_list=["csv1", "csv2"],
        css_content="/* css */",
        js_content="// js",
    )

    # Required keys
    assert context["title"] == "My Dashboard"
    assert context["subtitle"] == "Sub"
    assert context["include_dev_markup"] is True
    assert context["datasets"] == ["csv1", "csv2"]
    assert context["css_content"] == "/* css */"
    assert context["js_content"] == "// js"

    # Config is passed as JSON string
    decoded = json.loads(context["config_json"])
    assert decoded == full_config


def test_validate_inputs_rejects_invalid_types():
    gen = DashboardGenerator()

    # Invalid config type
    try:
        gen._validate_inputs(config="not-a-dict", datasets_list=[])
    except TypeError as exc:
        assert "config must be a dict" in str(exc)
    else:
        raise AssertionError("Expected TypeError for invalid config type")

    # Invalid datasets_list type
    try:
        gen._validate_inputs(config={}, datasets_list="not-a-list")
    except TypeError as exc:
        assert "datasets_list must be a list or tuple" in str(exc)
    else:
        raise AssertionError("Expected TypeError for invalid datasets_list type")

    # Invalid dataset element type
    try:
        gen._validate_inputs(config={}, datasets_list=[b"bytes-are-not-allowed"])
    except TypeError as exc:
        assert "must be a string containing CSV data" in str(exc)
    else:
        raise AssertionError("Expected TypeError for invalid dataset element type")

