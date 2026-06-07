import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from playwright.sync_api import Page

PLAYWRIGHT_NAV_TIMEOUT_MS = 60_000


def pytest_configure(config):
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def path_to_file_url(path: str) -> str:
    """Stable file:// URI on Linux and Windows (avoids file://// double-slash bugs)."""
    return Path(path).resolve().as_uri()


@pytest.fixture(scope="function", autouse=True)
def playwright_navigation_defaults(page: Page):
    """file:// dashboards load D3 from CDN; wait for DOM, not full network load."""
    page.set_default_navigation_timeout(PLAYWRIGHT_NAV_TIMEOUT_MS)
    page.set_default_timeout(30_000)
    original_goto = page.goto

    def goto(url: str, **kwargs):
        kwargs.setdefault("wait_until", "domcontentloaded")
        kwargs.setdefault("timeout", PLAYWRIGHT_NAV_TIMEOUT_MS)
        return original_goto(url, **kwargs)

    page.goto = goto
    yield


@pytest.fixture(scope="session")
def js_coverage_global():
    print("\n[DEBUG] Initializing global JS coverage buffer.")
    return []


@pytest.fixture(scope="function", autouse=True)
def capture_js_coverage(page: Page, js_coverage_global):
    browser_type = page.context.browser.browser_type.name
    if browser_type != "chromium":
        yield
        return

    if hasattr(page, "coverage"):
        page.coverage.start_js_coverage(reset_on_navigation=False)
        yield
        js_coverage_global.extend(page.coverage.stop_js_coverage())
        return

    session = page.context.new_cdp_session(page)
    session.send("Profiler.enable")
    session.send("Profiler.startPreciseCoverage", {"callCount": False, "detailed": True})
    yield
    res = session.send("Profiler.takePreciseCoverage")
    session.send("Profiler.stopPreciseCoverage")
    js_coverage_global.extend(res.get("result", []))


@pytest.fixture(scope="session", autouse=True)
def generate_js_report(js_coverage_global):
    yield

    total_entries = len(js_coverage_global)
    if total_entries == 0:
        print("[DEBUG] Stopping: no JS coverage entries to process.")
        return

    os.makedirs("output", exist_ok=True)
    raw_file = os.path.abspath("output/raw_v8_coverage.json")

    with open(raw_file, "w", encoding="utf-8") as f:
        json.dump(js_coverage_global, f)

    node_script = os.path.abspath(os.path.join("scripts", "generate_js_coverage.js"))

    if os.path.exists(node_script):
        node_exe = shutil.which("node")
        if not node_exe:
            print("[DEBUG] Node.js not found on PATH; skipping coverage merge script.")
        else:
            env = os.environ.copy()
            env.setdefault("PYTHONIOENCODING", "utf-8")
            result = subprocess.run(
                [node_exe, node_script, raw_file],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            print("[DEBUG] Node.js stdout:\n", result.stdout)
            if result.stderr:
                print("[DEBUG] Node.js stderr:\n", result.stderr)
            if result.returncode != 0:
                raise RuntimeError(
                    f"generate_js_coverage.js exited with {result.returncode}: {result.stderr or result.stdout}"
                )

    summary_file = "output/js-coverage-summary.json"
    if os.path.exists(summary_file):
        with open(summary_file, "r", encoding="utf-8") as f:
            content = f.read()

        if not content.strip():
            pct = 0.0
        else:
            summary = json.loads(content)
            raw_pct = summary.get("pct", 0)
            pct = float(raw_pct) if raw_pct != "" else 0.0

        import anybadge

        badge = anybadge.Badge(
            label="JS Coverage",
            value=f"{pct:.1f}%",
            default_color="gray",
            thresholds={50: "red", 70: "yellow", 90: "green"},
        )
        badge.write_badge("js-coverage.svg", overwrite=True)
        print(f"[DEBUG] JS coverage badge written: {pct:.1f}% -> js-coverage.svg")
