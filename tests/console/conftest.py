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

    # demo_data._dispatcher 是模块级单例，演示 profile 目录又是从
    # KINGDEE_CONSOLE_DB 的目录派生的（见 ontology_editor.runtime_profiles_dir）——
    # 不清掉的话，这个测试会拿到上一个测试（不同 tmp_path）缓存出来的
    # Dispatcher/Ontology，看不见自己这份干净的 profile。
    from kingdee_console import demo_data
    from kingdee_ontology.base.ontology import load as ontology_load
    demo_data.reset_dispatcher()
    ontology_load.cache_clear()

    yield path
    console_db.reset_cache()
    demo_data.reset_dispatcher()
    ontology_load.cache_clear()


@pytest.fixture
def seeded(console_database):
    """已经种好销售/仓库两个演示助理的 db。"""
    from kingdee_console import tenancy
    tenancy.ensure_seed_data()
    return console_database
