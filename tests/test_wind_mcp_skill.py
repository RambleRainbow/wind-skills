"""
wind-mcp-skill 专项测试

- smoke: 本地结构 / cli.mjs 存在性
- api: 需要 WIND_API_KEY 的端到端调用（TODO）
"""

import subprocess
from pathlib import Path

import pytest

WIND_MCP_DIR = Path(__file__).resolve().parent.parent / "skills" / "wind-mcp-skill"


class TestWindMcpSkillStructure:
    """wind-mcp-skill 特有的结构检查"""

    @pytest.mark.smoke
    def test_cli_script_exists(self):
        """cli.mjs 入口脚本必须存在"""
        assert (WIND_MCP_DIR / "scripts" / "cli.mjs").is_file()

    @pytest.mark.smoke
    def test_config_example_exists(self):
        """config.json.example 提供配置示范"""
        assert (WIND_MCP_DIR / "config.json.example").is_file()

    @pytest.mark.smoke
    def test_cli_help_runs(self):
        """cli.mjs --help 应可正常执行（不崩溃）"""
        result = subprocess.run(
            ["node", str(WIND_MCP_DIR / "scripts" / "cli.mjs"), "--help"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        # 允许 exit 0 或 exit 1（某些 CLI 框架 --help 返回 1）
        assert result.returncode in (0, 1), (
            f"cli.mjs --help 退出码异常: {result.returncode}\n"
            f"stderr: {result.stderr}"
        )


class TestWindMcpSkillApi:
    """需要 WIND_API_KEY 的端到端测试（占位）"""

    @pytest.mark.api
    def test_placeholder(self, require_api_key: str):
        """占位 — 后续补充真实 API 调用测试"""
        pytest.skip("API 端到端测试待实现")
