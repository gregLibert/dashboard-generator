import json
import os
import shutil
import subprocess

import pytest
from playwright.sync_api import Page


def pytest_configure(config):
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


@pytest.fixture(scope="session")
def js_coverage_global():
    print("\n[DEBUG] Initializing global JS coverage buffer.")
    return []


@pytest.fixture(scope="function", autouse=True)
def capture_js_coverage(page: Page, js_coverage_global):
    try:
        browser_name = page.context.browser.browser_type.name
        if browser_name != "chromium":
            yield
            return
    except Exception:
        yield
        return

    if not hasattr(page, "coverage"):
        try:
            session = page.context.new_cdp_session(page)
            session.send("Profiler.enable")
            session.send("Profiler.startPreciseCoverage", {"callCount": False, "detailed": True})
            yield
            res = session.send("Profiler.takePreciseCoverage")
            session.send("Profiler.stopPreciseCoverage")
            data = res.get("result", [])
            js_coverage_global.extend(data)
        except Exception:
            yield
        return

    coverage_started = False
    try:
        page.coverage.start_js_coverage(reset_on_navigation=False)
        coverage_started = True
    except Exception:
        pass

    yield

    if coverage_started:
        try:
            coverage_data = page.coverage.stop_js_coverage()
            js_coverage_global.extend(coverage_data)
        except Exception:
            pass


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
            try:
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

            except Exception as e:
                print(f"[DEBUG] subprocess.run failed: {e}")

    summary_file = "output/js-coverage-summary.json"
    if os.path.exists(summary_file):
        try:
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

        except Exception as e:
            print(f"[DEBUG] Badge generation failed: {e}")
