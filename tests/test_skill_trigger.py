"""
Skill 触发测试 — 验证 Claude Code 面对金融查询时能否正确触发 wind-mcp-skill

测试方法:
  1. 用 `claude -p "<prompt>" --output-format stream-json --verbose` 发送单行 prompt
  2. 解析 stream-json 输出，提取 tool_use 事件
  3. 断言 Claude 调用了 Bash 且命令中包含 `cli.mjs call <server_type> <tool_name>`

运行:
  pytest tests/test_skill_trigger.py -m trigger -v -s --timeout=300
  pytest tests/test_skill_trigger.py -m trigger -k "stock_kline" -v -s --timeout=300

环境要求:
  - `claude` CLI 可用
  - WIND_API_KEY 已配置（测试会实际调用 Wind API）
  - 当前目录有 .agents/skills/wind-mcp-skill（已安装 skill）

标记:
  - trigger: 所有触发测试
"""

import json
import subprocess
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pytest


# ── 常量 ──────────────────────────────────────────────────────

ROOT_DIR = Path(__file__).resolve().parent.parent
CLAUDE_TIMEOUT = 300  # seconds — Claude 多轮对话(list-tools + call)可达 3 分钟
MAX_BUDGET = 1.50     # USD — 单次测试的最大花费


# ── cli.mjs 错误码（出现在输出中表示调用失败）─────────────────

CLI_ERROR_CODES = [
    "KEY_MISSING", "KEY_INVALID", "UNKNOWN_SERVER_TYPE",
    "INVALID_PARAMS_JSON", "NETWORK_ERROR", "RATE_LIMIT_DAILY",
    "BALANCE_INSUFFICIENT", "MCP_PROTOCOL_ERROR", "SERVER_5XX",
    "RESPONSE_PARSE_ERROR",
]


# ── 数据结构 ──────────────────────────────────────────────────

@dataclass
class ToolCall:
    """从 stream-json 中提取的单次工具调用"""
    tool_name: str           # Claude 内置工具名，如 "Bash"
    tool_input: dict         # 工具输入参数
    tool_use_id: str = ""

    @property
    def bash_command(self) -> str:
        """如果是 Bash 工具，返回命令内容"""
        return self.tool_input.get("command", "")

    @property
    def calls_cli_mjs(self) -> bool:
        """命令中是否调用了 cli.mjs"""
        return "cli.mjs" in self.bash_command

    def extract_cli_args(self) -> Optional[dict]:
        """
        从 bash 命令中解析 cli.mjs 调用参数。

        支持两种格式:
          - node scripts/cli.mjs call ...
          - cd /path/to/skill && node scripts/cli.mjs call ...

        返回:
          {"action": "call", "server_type": "...", "tool_name": "...", "params_json": "..."}
          {"action": "list-tools", "server_type": "..."}
        """
        cmd = self.bash_command
        if "cli.mjs" not in cmd:
            return None

        # 匹配 call <server_type> <tool_name> '<json>'
        # 兼容单引号、双引号、无引号包裹的 JSON
        call_match = re.search(
            r'cli\.mjs\s+call\s+(\S+)\s+(\S+)\s+[\'"]?(\{.+?\})[\'"]?',
            cmd, re.DOTALL,
        )
        if call_match:
            return {
                "action": "call",
                "server_type": call_match.group(1),
                "tool_name": call_match.group(2),
                "params_json": call_match.group(3),
            }

        # 匹配 list-tools <server_type>
        list_match = re.search(
            r'cli\.mjs\s+list-tools\s+(\S+)',
            cmd,
        )
        if list_match:
            return {
                "action": "list-tools",
                "server_type": list_match.group(1),
            }

        return None


@dataclass
class ToolResult:
    """从 stream-json 中提取的工具执行结果"""
    tool_use_id: str
    content: str = ""       # 工具 stdout 输出文本
    is_error: bool = False

    @property
    def cli_ok(self) -> bool | None:
        """如果输出是 cli.mjs 的 JSON，返回 ok 字段；否则 None"""
        try:
            data = json.loads(self.content)
            return data.get("ok")
        except (json.JSONDecodeError, TypeError):
            return None

    @property
    def has_cli_error_code(self) -> str | None:
        """检查输出中是否包含 cli.mjs 错误码，返回匹配到的错误码"""
        for code in CLI_ERROR_CODES:
            if code in self.content:
                return code
        return None


@dataclass
class ClaudeRunResult:
    """一次 claude -p 运行的完整结果"""
    raw_lines: list[str] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    result_text: str = ""
    is_error: bool = False
    total_cost_usd: float = 0.0
    session_id: str = ""
    num_turns: int = 0
    duration_ms: int = 0

    @property
    def cli_mjs_calls(self) -> list[ToolCall]:
        """所有调用了 cli.mjs 的 Bash 工具调用"""
        return [tc for tc in self.tool_calls if tc.calls_cli_mjs]

    @property
    def cli_call_actions(self) -> list[dict]:
        """所有 cli.mjs call 的解析结果"""
        results = []
        for tc in self.cli_mjs_calls:
            args = tc.extract_cli_args()
            if args and args["action"] == "call":
                results.append(args)
        return results

    def has_server_type(self, server_type: str) -> bool:
        """是否调用了指定 server_type"""
        return any(
            a["server_type"] == server_type
            for a in self.cli_call_actions
        )

    def has_tool(self, tool_name: str) -> bool:
        """是否调用了指定工具"""
        return any(
            a["tool_name"] == tool_name
            for a in self.cli_call_actions
        )

    def get_result_for_call(self, tool_use_id: str) -> Optional[ToolResult]:
        """根据 tool_use_id 找到对应的 tool_result"""
        for tr in self.tool_results:
            if tr.tool_use_id == tool_use_id:
                return tr
        return None

    @property
    def cli_call_results(self) -> list[tuple[dict, Optional[ToolResult]]]:
        """返回 (cli_call_action, tool_result) 配对列表"""
        pairs = []
        for tc in self.cli_mjs_calls:
            args = tc.extract_cli_args()
            if args and args["action"] == "call":
                tr = self.get_result_for_call(tc.tool_use_id)
                pairs.append((args, tr))
        return pairs

    @property
    def any_cli_ok(self) -> bool:
        """是否有任何一次 cli.mjs call 返回 ok:true"""
        for _, tr in self.cli_call_results:
            if tr and tr.cli_ok is True:
                return True
        return False

    def summary(self) -> str:
        """测试报告摘要"""
        lines = [
            f"Session:  {self.session_id}",
            f"Turns:    {self.num_turns}",
            f"Duration: {self.duration_ms / 1000:.1f}s",
            f"Cost:     ${self.total_cost_usd:.4f}",
            f"Tools:    {len(self.tool_calls)} calls ({len(self.cli_mjs_calls)} cli.mjs)",
        ]
        for i, (a, tr) in enumerate(self.cli_call_results):
            ok_flag = "✅" if (tr and tr.cli_ok) else "❓"
            err = f" ⚠ {tr.has_cli_error_code}" if (tr and tr.has_cli_error_code) else ""
            lines.append(
                f"  call[{i}]: {ok_flag} {a['server_type']}.{a['tool_name']}{err}"
            )
        return "\n".join(lines)


# ── 核心：运行 Claude CLI 并解析输出 ─────────────────────────

def run_claude_prompt(prompt: str, timeout: int = CLAUDE_TIMEOUT) -> ClaudeRunResult:
    """
    运行 claude -p 并解析 stream-json 输出。

    关键参数:
      --print                         非交互模式
      --output-format stream-json     能看到每个 tool_use 事件
      --verbose                       stream-json 必须
      --max-budget-usd                控制花费
      --dangerously-skip-permissions  跳过权限确认（CI/测试场景）
      --tools "Bash,Read"             只允许 Bash 和 Read（skill 通过 Bash 调 cli.mjs）
    """
    cmd = [
        "claude",
        "-p", prompt,
        "--output-format", "stream-json",
        "--verbose",
        "--max-budget-usd", str(MAX_BUDGET),
        "--dangerously-skip-permissions",
        "--tools", "Bash,Read",
    ]

    result = subprocess.run(
        cmd,
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    return _parse_stream_json(result.stdout)


def _parse_stream_json(output: str) -> ClaudeRunResult:
    """解析 claude --output-format stream-json 的输出"""
    run = ClaudeRunResult()

    for line in output.strip().splitlines():
        line = line.strip()
        if not line:
            continue

        run.raw_lines.append(line)

        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        event_type = event.get("type", "")

        # 提取 tool_use（在 assistant message 的 content 块中）
        if event_type == "assistant":
            msg = event.get("message", {})
            for block in msg.get("content", []):
                if block.get("type") == "tool_use":
                    tc = ToolCall(
                        tool_name=block.get("name", ""),
                        tool_input=block.get("input", {}),
                        tool_use_id=block.get("id", ""),
                    )
                    run.tool_calls.append(tc)

        # 提取 tool_result（Bash/Read 工具执行后的返回值）
        # stream-json 格式: tool results 在 type="user" 事件的
        # message.content[] 中，每个 block 的 type="tool_result"
        elif event_type == "user":
            msg = event.get("message", {})
            for block in msg.get("content", []):
                if block.get("type") == "tool_result":
                    tool_use_id = block.get("tool_use_id", "")
                    content_text = ""
                    is_err = block.get("is_error", False)
                    raw_content = block.get("content", "")
                    if isinstance(raw_content, str):
                        content_text = raw_content
                    elif isinstance(raw_content, list):
                        content_text = "\n".join(
                            b.get("text", "") for b in raw_content
                            if isinstance(b, dict)
                        )
                    if tool_use_id:
                        run.tool_results.append(ToolResult(
                            tool_use_id=tool_use_id,
                            content=content_text,
                            is_error=is_err,
                        ))

        # 提取最终结果
        elif event_type == "result":
            run.result_text = event.get("result", "")
            run.is_error = event.get("is_error", False)
            run.total_cost_usd = event.get("total_cost_usd", 0.0)
            run.session_id = event.get("session_id", "")
            run.num_turns = event.get("num_turns", 0)
            run.duration_ms = event.get("duration_ms", 0)

    return run


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture(scope="session")
def check_claude_cli():
    """验证 claude CLI 可用"""
    result = subprocess.run(
        ["claude", "--version"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        pytest.skip("claude CLI 不可用")


@pytest.fixture(scope="session")
def check_skill_installed():
    """验证 wind-mcp-skill 已安装到当前项目"""
    skill_path = ROOT_DIR / ".agents" / "skills" / "wind-mcp-skill" / "SKILL.md"
    if not skill_path.is_file():
        pytest.skip("wind-mcp-skill 未安装到 .agents/skills/")


# ── 测试用例定义 ──────────────────────────────────────────────

# 每个用例: (test_id, prompt, expected_server_type, expected_tool_name)
# 验证点: cli.mjs 返回 ok:true 且无错误码即可，不检查具体返回内容
TRIGGER_CASES = [
    # ── stock_data 行情类 ──
    (
        "stock_kline",
        "用 wind-mcp-skill 查贵州茅台最近 5 个交易日的日 K 线数据，只给我数据不要分析",
        "stock_data",
        "get_stock_kline",
    ),
    # ── stock_data NL 类 ──
    (
        "stock_basicinfo",
        "用 wind-mcp-skill 查询 600519.SH 的公司基本档案信息，只返回数据",
        "stock_data",
        "get_stock_basicinfo",
    ),
    # ── fund_data NL 类 ──
    (
        "fund_info",
        "用 wind-mcp-skill 查 005827.OF 易方达蓝筹精选的基金档案，只返回数据",
        "fund_data",
        "get_fund_info",
    ),
    # ── analytics_data 通用 ──
    (
        "analytics_general",
        "用 wind-mcp-skill 的 analytics_data 查 中证500 最近一周的表现，只返回数据",
        "analytics_data",
        "get_financial_data",
    ),
]


# ── 测试类 ────────────────────────────────────────────────────

class TestSkillTrigger:
    """
    验证 Claude Code 面对金融查询时:
    1. 触发了 wind-mcp-skill（通过 Bash 调用 cli.mjs）
    2. 选择了正确的 server_type
    3. 调用了正确的 tool_name
    4. cli.mjs 返回 ok:true（数据成功获取）
    5. Claude 最终回复包含预期的金融数据关键词
    """

    @pytest.mark.trigger
    @pytest.mark.parametrize(
        "test_id, prompt, expected_server, expected_tool",
        TRIGGER_CASES,
        ids=[c[0] for c in TRIGGER_CASES],
    )
    def test_trigger_correct_tool(
        self,
        check_claude_cli,
        check_skill_installed,
        require_api_key,
        test_id: str,
        prompt: str,
        expected_server: str,
        expected_tool: str,
    ):
        """Claude 应该通过 cli.mjs call 调用正确的 server_type + tool_name，并获得有效数据"""
        result = run_claude_prompt(prompt)

        # 打印摘要（-s 模式下可见）
        print(f"\n{'=' * 60}")
        print(f"[{test_id}] {prompt[:50]}...")
        print(result.summary())
        print(f"{'=' * 60}")

        # 1. Claude 不应报错（budget exceeded 除外）
        if result.is_error:
            error_text = str(result.result_text).lower()
            if "budget" not in error_text:
                pytest.fail(
                    f"Claude 运行出错: {result.result_text}\n"
                    f"Session: {result.session_id}"
                )

        # 2. 必须调用了 cli.mjs
        cli_calls = result.cli_mjs_calls
        assert len(cli_calls) > 0, (
            f"Claude 未调用 cli.mjs！\n"
            f"所有工具调用:\n"
            + "\n".join(
                f"  [{tc.tool_name}] {tc.bash_command[:120]}"
                for tc in result.tool_calls
            )
            + f"\nSession: {result.session_id}"
        )

        # 3. 提取所有 call 动作
        call_actions = result.cli_call_actions
        assert len(call_actions) > 0, (
            f"Claude 调用了 cli.mjs 但未执行 'call' 命令\n"
            f"cli.mjs 命令:\n"
            + "\n".join(f"  {tc.bash_command}" for tc in cli_calls)
            + f"\nSession: {result.session_id}"
        )

        # 4. 验证 server_type
        server_types = [a["server_type"] for a in call_actions]
        assert expected_server in server_types, (
            f"期望 server_type={expected_server}，实际={server_types}\n"
            f"Session: {result.session_id}"
        )

        # 5. 验证 tool_name
        tool_names = [a["tool_name"] for a in call_actions]
        assert expected_tool in tool_names, (
            f"期望 tool_name={expected_tool}，实际={tool_names}\n"
            f"Session: {result.session_id}"
        )

        # 6. 验证 cli.mjs 返回结果（ok:true，无错误码）
        call_results = result.cli_call_results
        if call_results:
            # 至少有一次 call 返回了 ok:true
            assert result.any_cli_ok, (
                f"所有 cli.mjs call 均未返回 ok:true\n"
                + "\n".join(
                    f"  {a['server_type']}.{a['tool_name']}: "
                    f"ok={tr.cli_ok if tr else '?'}, "
                    f"error={tr.has_cli_error_code if tr else '?'}"
                    for a, tr in call_results
                )
                + f"\nSession: {result.session_id}"
            )

            # 不应出现错误码
            for action, tr in call_results:
                if tr and tr.has_cli_error_code:
                    pytest.fail(
                        f"cli.mjs 返回错误码: {tr.has_cli_error_code}\n"
                        f"调用: {action['server_type']}.{action['tool_name']}\n"
                        f"输出前 300 字符: {tr.content[:300]}\n"
                        f"Session: {result.session_id}"
                    )

        # 7. 最终回复不应包含 MCP 错误标记
        final_text = result.result_text or ""
        assert "❌ MCP 错误" not in final_text, (
            f"Claude 最终回复中包含 MCP 错误\n"
            f"回复前 500 字符: {final_text[:500]}\n"
            f"Session: {result.session_id}"
        )
