"""kingdee_console 测试的公共夹具 —— 每个测试一个干净的 sqlite 文件。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from kingdee_console import db as console_db  # noqa: E402


@pytest.fixture
def console_database(tmp_path, monkeypatch):
    path = tmp_path / "console_test.db"
    monkeypatch.setenv("KINGDEE_CONSOLE_DB", str(path))
    console_db.reset_cache()
    yield path
    console_db.reset_cache()


@pytest.fixture
def seeded(console_database):
    """已经种好销售/仓库两个演示助理的 db。"""
    from kingdee_console import tenancy
    tenancy.ensure_seed_data()
    return console_database
