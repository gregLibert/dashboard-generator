import json

import pytest

from dashboard_engine.generator import DashboardGenerator


def test_build_full_config_adds_generation_date():
    config = {"title": "Test", "widgets": []}

    full = DashboardGenerator._build_full_config(config)

    # Original keys stay intact
    assert full["title"] == "Test"
    assert full["widgets"] == []

    # Enriched metadata
    assert "generation_date" in full
    assert isinstance(full["generation_date"], str)
    assert len(full["generation_date"]) == 8  # YYYYMMDD


def test_build_context_structure_is_stable():
    config = {"title": "My Dashboard", "subtitle": "Sub", "dev_mode": True}
    full_config = {"foo": "bar"}

    datasets_norm = [
        {"encoding": None, "payload": "csv1"},
        {"encoding": None, "payload": "csv2"},
    ]
    context = DashboardGenerator._build_context(
        config=config,
        full_config=full_config,
        datasets_normalized=datasets_norm,
        css_content="/* css */",
        js_content="// js",
    )

    # Required keys
    assert context["title"] == "My Dashboard"
    assert context["subtitle"] == "Sub"
    assert context["include_dev_markup"] is True
    assert context["datasets"] == datasets_norm
    assert context["css_content"] == "/* css */"
    assert context["js_content"] == "// js"

    # Config is passed as JSON string
    decoded = json.loads(context["config_json"])
    assert decoded == full_config


_VALIDATE_INPUTS_CASES = [
    pytest.param(
        {"config": "not-a-dict", "datasets_list": []},
        TypeError,
        "config must be a dict",
        id="invalid_config_type",
    ),
    pytest.param(
        {"config": {}, "datasets_list": "not-a-list"},
        TypeError,
        "datasets_list must be a list or tuple",
        id="invalid_datasets_list_type",
    ),
    pytest.param(
        {"config": {}, "datasets_list": [b"bytes-are-not-allowed"]},
        TypeError,
        "must be a string containing CSV data",
        id="invalid_dataset_element_type",
    ),
]


@pytest.mark.parametrize("kwargs,exc_type,msg_substr", _VALIDATE_INPUTS_CASES)
def test_validate_inputs_rejects_invalid_types(kwargs, exc_type, msg_substr):
    gen = DashboardGenerator()
    with pytest.raises(exc_type) as exc_info:
        gen._validate_inputs(**kwargs)
    assert msg_substr in str(exc_info.value)
