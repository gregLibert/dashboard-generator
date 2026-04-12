from dashboard_engine.generator import DashboardGenerator


def test_js_assets_optimization_filters_unused_widgets():
    """collect_js_asset_paths only includes mandatory JS plus declared widget types."""
    config_sankey_only = {"widgets": [{"type": "sankey"}]}

    ordered_paths, need_sankey = DashboardGenerator.collect_js_asset_paths(config_sankey_only)

    assert need_sankey is True
    assert "js/sankey_widget.js" in ordered_paths
    assert "js/stacked_area_widget.js" not in ordered_paths
    assert "js/sunburst_widget.js" not in ordered_paths
    assert "js/utils.js" in ordered_paths
    assert "js/main.js" in ordered_paths


def test_full_bundle_includes_all_widget_modules():
    """Explicit full bundle (used by Playwright HTML) lists every widget file and sankey."""
    ordered_paths, need_sankey = DashboardGenerator.collect_js_asset_paths_full_bundle()
    assert need_sankey is True
    assert "js/main.js" in ordered_paths
    assert "js/bubble_widget.js" in ordered_paths
    assert "js/sankey_widget.js" in ordered_paths