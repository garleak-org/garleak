# SPDX-License-Identifier: AGPL-3.0-or-later
import os
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE_CACHE = FIXTURES / "cache"
SCHEMA = Path(__file__).parent.parent / "schema" / "report.v1.json"


def pytest_addoption(parser):
    parser.addoption("--network", action="store_true", default=False,
                     help="run tests marked 'network' (they call live services)")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--network") or os.environ.get("CITECHECK_NETWORK_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="live network test; opt in with --network or CITECHECK_NETWORK_TESTS=1")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture(autouse=True)
def _no_user_env(monkeypatch):
    """Keep tests independent of the developer's environment (tokens, mailto, cache dir)."""
    for var in ("CITECHECK_MAILTO", "ADS_TOKEN", "OPENALEX_API_KEY", "CITECHECK_CACHE_DIR"):
        monkeypatch.delenv(var, raising=False)
