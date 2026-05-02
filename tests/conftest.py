"""
wind-skills 全局 pytest fixtures
"""

import os
import json
from pathlib import Path

import pytest

# ── 路径常量 ──────────────────────────────────────────────────

ROOT_DIR = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT_DIR / "skills"


# ── fixtures ──────────────────────────────────────────────────

@pytest.fixture(scope="session")
def root_dir() -> Path:
    """项目根目录"""
    return ROOT_DIR


@pytest.fixture(scope="session")
def skills_dir() -> Path:
    """skills/ 目录"""
    return SKILLS_DIR


@pytest.fixture(scope="session")
def all_skill_names() -> list[str]:
    """列出 skills/ 下所有 skill 名称（子目录名）"""
    return sorted(
        d.name
        for d in SKILLS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )


@pytest.fixture(scope="session")
def wind_api_key() -> str | None:
    """
    尝试从环境变量 / 全局配置读取 WIND_API_KEY。
    返回 None 表示未配置（配合 pytest.mark.api 跳过需要 Key 的测试）。
    """
    # 1) 环境变量
    key = os.environ.get("WIND_API_KEY")
    if key:
        return key

    # 2) 全局配置 ~/.wind-aimarket/config
    global_config = Path.home() / ".wind-aimarket" / "config"
    if global_config.exists():
        for line in global_config.read_text().splitlines():
            if line.startswith("WIND_API_KEY="):
                return line.split("=", 1)[1].strip()

    return None


@pytest.fixture(scope="session")
def require_api_key(wind_api_key: str | None) -> str:
    """需要 API Key 的测试可依赖此 fixture，无 Key 时自动 skip"""
    if not wind_api_key:
        pytest.skip("WIND_API_KEY 未配置，跳过需要 API Key 的测试")
    return wind_api_key
