"""The dashboard runs on the committed reports/ files (skipped where Streamlit is not installed)."""
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"


def test_dashboard_renders_every_tab_without_errors():
    app = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not app.exception
    assert len(app.tabs) == 5
    assert app.metric[0].label == "PM2.5 trend, 2015-2025"


def test_outlook_scenarios_can_be_selected():
    app = AppTest.from_file(str(APP), default_timeout=60).run()
    box = app.selectbox[0]
    for option in box.options:
        app = box.set_value(option).run()
        assert not app.exception
        box = app.selectbox[0]
