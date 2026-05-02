"""
Smoke tests — 校验 skills/ 目录结构完整性

无需 API Key、无需 MCP server，仅检查文件系统。
"""

from pathlib import Path

import pytest


# ── 参数化：每个 skill 都跑一遍 ───────────────────────────────

@pytest.fixture(params=[
    d.name
    for d in (Path(__file__).resolve().parent.parent / "skills").iterdir()
    if d.is_dir() and not d.name.startswith(".")
])
def skill_dir(request, skills_dir: Path) -> Path:
    return skills_dir / request.param


# ── 测试用例 ──────────────────────────────────────────────────

class TestSkillStructure:
    """每个 skill 必须满足的目录规范"""

    @pytest.mark.smoke
    def test_skill_md_exists(self, skill_dir: Path):
        """SKILL.md 是 skill 协议的必要文件"""
        assert (skill_dir / "SKILL.md").is_file(), (
            f"{skill_dir.name}/ 缺少 SKILL.md"
        )

    @pytest.mark.smoke
    def test_skill_md_not_empty(self, skill_dir: Path):
        """SKILL.md 不能为空"""
        skill_md = skill_dir / "SKILL.md"
        if skill_md.is_file():
            content = skill_md.read_text(encoding="utf-8").strip()
            assert len(content) > 0, f"{skill_dir.name}/SKILL.md 为空"

    @pytest.mark.smoke
    def test_skill_md_has_frontmatter(self, skill_dir: Path):
        """SKILL.md 应以 YAML frontmatter（---）开头"""
        skill_md = skill_dir / "SKILL.md"
        if skill_md.is_file():
            content = skill_md.read_text(encoding="utf-8")
            assert content.startswith("---"), (
                f"{skill_dir.name}/SKILL.md 缺少 YAML frontmatter"
            )
