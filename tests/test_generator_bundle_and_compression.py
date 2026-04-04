"""Table-driven tests for JS bundle selection and optional dataset compression."""
import base64
import gzip
import re

import pytest

from dashboard_engine.generator import (
    CSV_ENCODING_GZIP_BASE64,
    DashboardGenerator,
    WIDGET_TYPE_TO_JS_FILE,
    normalize_dataset_for_template,
)


def _minimal_config(widgets):
    return {"title": "T", "widgets": widgets}


@pytest.mark.parametrize(
    "widgets,required_substrings,forbidden_substrings",
    [
        (
            [],
            ["// --- js/utils.js ---", "// --- js/base_widget.js ---", "// --- js/main.js ---"],
            ["// --- js/sankey_widget.js ---", "// --- js/bubble_widget.js ---"],
        ),
        (
            [{"type": "bubble", "title": "B", "datasetIndex": 0}],
            ["// --- js/bubble_widget.js ---"],
            ["// --- js/sankey_widget.js ---", "// --- js/financial_sankey_widget.js ---"],
        ),
        (
            [{"type": "sankey", "title": "S", "datasetIndex": 0}],
            ["// --- js/sankey_widget.js ---", "d3-sankey"],
            ["// --- js/bubble_widget.js ---"],
        ),
        (
            [{"type": "financial_sankey", "title": "F", "datasetIndex": 0}],
            ["// --- js/financial_sankey_widget.js ---", "d3-sankey"],
            ["// --- js/sankey_widget.js ---"],
        ),
        (
            [
                {"type": "sankey", "title": "S", "datasetIndex": 0},
                {"type": "bubble", "title": "B", "datasetIndex": 0},
            ],
            [
                "// --- js/sankey_widget.js ---",
                "// --- js/bubble_widget.js ---",
                "d3-sankey",
            ],
            ["// --- js/sunburst_widget.js ---"],
        ),
        (
            [{"type": "nested_treemap", "title": "T", "datasetIndex": 0}],
            ["// --- js/treemap_widget.js ---"],
            ["// --- js/bubble_widget.js ---"],
        ),
    ],
    ids=[
        "no_widgets",
        "bubble_only",
        "sankey_only",
        "financial_sankey_only",
        "sankey_and_bubble",
        "nested_treemap",
    ],
)
def test_generated_html_includes_only_expected_js_modules(
    widgets, required_substrings, forbidden_substrings
):
    gen = DashboardGenerator()
    html = gen.generate(_minimal_config(widgets), ["a,b\n1"])
    for s in required_substrings:
        assert s in html, "missing marker: {!r}".format(s)
    for s in forbidden_substrings:
        assert s not in html, "unexpected marker: {!r}".format(s)


@pytest.mark.parametrize("wtype", sorted(WIDGET_TYPE_TO_JS_FILE.keys()))
def test_each_known_widget_type_loads_its_js_file(wtype):
    gen = DashboardGenerator()
    html = gen.generate(_minimal_config([{"type": wtype, "title": "x", "datasetIndex": 0}]), ["x\n1"])
    marker = "// --- {} ---".format(WIDGET_TYPE_TO_JS_FILE[wtype])
    assert marker in html


@pytest.mark.parametrize("bad_type", ["not_a_widget", "", "Treemap"])
def test_unknown_widget_type_raises(bad_type):
    gen = DashboardGenerator()
    with pytest.raises(ValueError) as ei:
        gen.generate(_minimal_config([{"type": bad_type, "title": "x"}]), ["a\n1"])
    assert "Unknown widget type" in str(ei.value)


def test_widgets_must_be_list_when_provided():
    gen = DashboardGenerator()
    with pytest.raises(TypeError) as ei:
        gen.generate({"title": "x", "widgets": "nope"}, ["a\n1"])
    assert "widgets" in str(ei.value)


@pytest.mark.parametrize("compress_data", [False, True], ids=["plain", "gzip_base64"])
def test_compress_data_toggle_on_embedded_dataset(compress_data):
    gen = DashboardGenerator()
    csv_text = "col1,col2\nhello,world\n"
    html = gen.generate({"title": "x", "widgets": []}, [csv_text], compress_data=compress_data)
    # Match only the dataset script tag (main.js mentions data-csv-encoding in error strings).
    ds0_open = re.search(r'<script[^>]*\bid="dataset-0"[^>]*>', html)
    assert ds0_open, "expected dataset-0 script tag"
    if compress_data:
        assert 'data-csv-encoding="{}"'.format(CSV_ENCODING_GZIP_BASE64) in ds0_open.group(0)
        assert "hello,world" not in html.split("</script>", 1)[0]
    else:
        assert "data-csv-encoding" not in ds0_open.group(0)
        assert "hello,world" in html


@pytest.mark.parametrize("compress_data", [False, True])
def test_normalize_dataset_roundtrip_when_compressed(compress_data):
    raw = "m1,m2\n10,20\n"
    packed = normalize_dataset_for_template(raw, compress_data)
    if not compress_data:
        assert packed == {"encoding": None, "payload": raw}
        return
    assert packed["encoding"] == CSV_ENCODING_GZIP_BASE64
    out = gzip.decompress(base64.b64decode(packed["payload"])).decode("utf-8")
    assert out == raw


def test_duplicate_widget_type_includes_js_module_once():
    gen = DashboardGenerator()
    html = gen.generate(
        _minimal_config(
            [
                {"type": "bubble", "title": "B1", "datasetIndex": 0},
                {"type": "bubble", "title": "B2", "datasetIndex": 0},
            ]
        ),
        ["a,b\n1"],
    )
    assert html.count("// --- js/bubble_widget.js ---") == 1


def test_collect_js_asset_paths_order_and_sankey_flag():
    cfg = _minimal_config(
        [
            {"type": "heatmap", "title": "h"},
            {"type": "sankey", "title": "s"},
        ]
    )
    paths, need_sankey = DashboardGenerator.collect_js_asset_paths(cfg)
    assert need_sankey is True
    assert paths[0] == "js/utils.js"
    assert paths[1] == "js/base_widget.js"
    assert paths[-1] == "js/main.js"
    assert paths.index("js/heatmap_widget.js") < paths.index("js/sankey_widget.js")
    assert paths.index("js/sankey_widget.js") < paths.index("js/main.js")
