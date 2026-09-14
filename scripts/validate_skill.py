#!/usr/bin/env python3
"""Validate the relationship-mentor skill without third-party packages.

Checks: frontmatter contract, SKILL.md size budget, required file inventory,
retrieval-first behavior markers, runtime content boundaries, local markdown
links and leftover template placeholders.

Usage:
    python scripts/validate_skill.py
"""

from __future__ import annotations

import re
from math import ceil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ERRORS: list[str] = []

SKILL_NAME = "relationship-mentor"
SKILL_MAX_LINES = 200
SKILL_MAX_CHARACTERS = 14_000
SKILL_MAX_APPROX_TOKENS = 10_000

# GitHub web upload caps a single file at 25MB; keep the shipped DB well under it.
MAX_SHIPPED_FILE_MB = 25

# Directories that hold backups, not runtime content.
EXCLUDED_PARTS = {".backup", ".git", "__pycache__", ".workbuddy"}

REQUIRED_CORPUS = (
    "00_总纲与诊断框架.md",
    "03_技法清单.md",
    "04_话术库.md",
    "05_案例库.md",
    "06_概念与原则.md",
    "07_语料地图.md",
)

REQUIRED_KNOWLEDGE = (
    "01-证据分级与内容边界.md",
    "05-PUA操控与伦理替代.md",
    "08-同意边界性与亲密.md",
    "09-在线约会与数字关系.md",
    "17-中国法律安全与危机转介.md",
    "20-经典社交体系的机制、证据与风险边界.md",
)

REQUIRED_PRACTICAL = (
    "00-导读与使用分级.md",
    "关系投入失衡：互惠判断、降级投入与退出决策.md",
    "场景感、松弛感与社交校准：从接话到关系推进.md",
    "实战话术编排器：从一句回复到后续分支.md",
    "主动表达、第一次见面与自然接触.md",
    "自然流、内在状态与结构化互动：伦理能力转译.md",
    "ChatLab聊天记录分析适配.md",
    "长期记忆与关系档案.md",
    "公开表达案例的伦理转译.md",
)


def require(path: str) -> Path:
    target = ROOT / path
    if not target.exists():
        ERRORS.append(f"missing required path: {path}")
    return target


def read_description(frontmatter: str) -> str:
    """Read `description:`, supporting inline values and `>` / `>-` / `|` block scalars."""
    lines = frontmatter.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"^description:\s*(.*)$", line)
        if not match:
            continue
        value = match.group(1).strip()
        if value not in {">", ">-", "|", "|-", ">+", "|+"}:
            return value
        block: list[str] = []
        for follow in lines[index + 1 :]:
            if not follow.strip():
                break
            if not follow.startswith(" ") and not follow.startswith("\t"):
                break
            block.append(follow.strip())
        return " ".join(block).strip()
    return ""


def validate_frontmatter() -> None:
    skill = require("SKILL.md")
    if not skill.is_file():
        return

    content = skill.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not match:
        ERRORS.append("SKILL.md has invalid YAML frontmatter boundaries")
        return

    frontmatter = match.group(1)
    keys = re.findall(r"^([A-Za-z0-9_-]+):", frontmatter, re.MULTILINE)
    if keys[:2] != ["name", "description"]:
        ERRORS.append(f"SKILL.md frontmatter must start with name, description; got {keys[:2]}")

    name_match = re.search(r"^name:\s*([^\n]+)$", frontmatter, re.MULTILINE)
    name = name_match.group(1).strip() if name_match else ""
    description = read_description(frontmatter)
    if name != SKILL_NAME or not re.fullmatch(r"[a-z0-9-]{1,64}", name):
        ERRORS.append(f"invalid skill name: {name!r}")
    if not description or len(description) > 1024 or "<" in description or ">" in description:
        ERRORS.append("description is empty, too long, or contains angle brackets")


def approximate_token_count(content: str) -> int:
    """Return a conservative, dependency-free budget estimate for mixed Chinese text."""
    cjk = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", content))
    latin_words = len(re.findall(r"[A-Za-z0-9_]+", content))
    other = len(re.findall(r"[^\sA-Za-z0-9_\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", content))
    return cjk + ceil(latin_words * 1.3) + ceil(other / 4)


def validate_skill_budget() -> None:
    skill = ROOT / "SKILL.md"
    if not skill.is_file():
        return

    content = skill.read_text(encoding="utf-8")
    lines = len(content.splitlines())
    characters = len(content)
    approx_tokens = approximate_token_count(content)
    if lines > SKILL_MAX_LINES:
        ERRORS.append(f"SKILL.md exceeds {SKILL_MAX_LINES} lines: {lines}")
    if characters > SKILL_MAX_CHARACTERS:
        ERRORS.append(f"SKILL.md exceeds {SKILL_MAX_CHARACTERS} characters: {characters}")
    if approx_tokens > SKILL_MAX_APPROX_TOKENS:
        ERRORS.append(
            f"SKILL.md exceeds approximate token budget {SKILL_MAX_APPROX_TOKENS}: {approx_tokens}"
        )


def validate_inventory() -> None:
    require("SKILL.md")
    require("AGENT.md")          # platform-agnostic source of truth
    require("AGENTS.md")         # cross-agent convention entry point
    require("CLAUDE.md")
    require("system_prompt.md")
    require("README.md")
    require("LICENSE")
    require("mcp.example.json")
    require("database/mentor.db")
    require("scripts/query.py")
    require("scripts/memory_store.py")
    require("scripts/object_learn.py")
    require("scripts/mcp_server.py")
    require("scripts/install.py")
    for filename in REQUIRED_CORPUS:
        require(f"references/corpus/{filename}")
    for filename in REQUIRED_KNOWLEDGE:
        require(f"references/knowledge/{filename}")
    for filename in REQUIRED_PRACTICAL:
        require(f"references/practical/{filename}")


def validate_upload_budget() -> None:
    """GitHub web upload rejects any single file above 25MB."""
    total = 0
    for path, relative in iter_runtime_files():
        if not path.is_file() or EXCLUDED_PARTS.intersection(relative.parts):
            continue
        size = path.stat().st_size
        total += size
        if size > MAX_SHIPPED_FILE_MB * 1024 * 1024:
            ERRORS.append(
                f"file exceeds {MAX_SHIPPED_FILE_MB}MB GitHub web-upload limit: "
                f"{relative} ({size / 1048576:.1f} MB)"
            )
    if total > 200 * 1024 * 1024:
        ERRORS.append(f"shipped content is {total / 1048576:.0f} MB, too heavy for a web upload")
    return total


def validate_routes_and_regressions() -> None:
    skill = ROOT / "SKILL.md"
    if not skill.is_file():
        return

    content = skill.read_text(encoding="utf-8")

    required_routes = (
        "references/corpus/00_总纲与诊断框架.md",
        "references/corpus/07_语料地图.md",
        "references/knowledge/05-PUA操控与伦理替代.md",
        "references/knowledge/17-中国法律安全与危机转介.md",
        "references/practical/00-导读与使用分级.md",
        "references/practical/实战话术编排器：从一句回复到后续分支.md",
        "references/practical/关系投入失衡：互惠判断、降级投入与退出决策.md",
        "references/practical/长期记忆与关系档案.md",
        "按需读 1–2 份，非必需",
    )
    for route in required_routes:
        if route not in content:
            ERRORS.append(f"SKILL.md missing required reference route: {route}")

    regression_markers = (
        # retrieval-first: the non-negotiable rule of this skill
        "第 0 步：想任何问题之前，先查库（硬性，贯穿全程）",
        "每一次要给出判断、方法、话术或结论之前，都得先有检索结果摆在面前",
        "没查过就说，等于编",
        "凭记忆或直觉作答视为违规",
        "scripts/query.py",
        # per-object learning
        "scripts/object_learn.py brief --subject A",
        "profile --subject A                  # 完整画像与历次归档",
        "已验证有效",
        "不得外推成人格、动机",
        "归档前报备一句",
        "不在仓库里，不会跟着 push 到 GitHub",
        # diagnosis discipline
        "不要跨阶段给建议",
        "最多 3 个问题",
        "自检与退出",
        # evidence boundaries
        "说话人映射不明先问",
        "不声称能读取或导出微信、QQ 记录",
        # long-term memory consent
        "首次明确同意后才启用",
        "不得从名字或旧案例推测补事实",
        # red lines
        "对方明确表示不想发展、要求别联系、反复表示不欢迎时停止推进",
        '不承诺"照做一定能追到 / 挽回"',
        "PUA 黑话必须转译",
        "先确认当下安全",
    )
    for marker in regression_markers:
        if marker not in content:
            ERRORS.append(f"SKILL.md missing required behavior boundary: {marker}")


def iter_runtime_files():
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if EXCLUDED_PARTS.intersection(relative.parts):
            continue
        yield path, relative


def validate_runtime_boundaries() -> None:
    runtime_roots = (
        ROOT / "SKILL.md",
        ROOT / "AGENT.md",
        ROOT / "AGENTS.md",
        ROOT / "CLAUDE.md",
        ROOT / "system_prompt.md",
        ROOT / "mcp.example.json",
        ROOT / "references",
        ROOT / "scripts",
    )
    forbidden_parts = {"research", "documentation", "__pycache__"}
    for runtime_root in runtime_roots:
        if not runtime_root.exists():
            continue
        paths = (runtime_root,) if runtime_root.is_file() else runtime_root.rglob("*")
        for path in paths:
            relative = path.relative_to(ROOT)
            if EXCLUDED_PARTS.intersection(relative.parts):
                continue
            if forbidden_parts.intersection(relative.parts):
                ERRORS.append(f"non-runtime content nested inside runtime allowlist: {relative}")
            if path.is_file() and path.suffix in {".pyc", ".pyo"}:
                ERRORS.append(f"compiled artifact found: {relative}")


def validate_markdown_links() -> None:
    link_pattern = re.compile(r"\]\(([^)]+)\)")
    for path, relative in iter_runtime_files():
        if not path.is_file() or path.suffix != ".md":
            continue
        text = path.read_text(encoding="utf-8")
        for raw_target in link_pattern.findall(text):
            target = raw_target.strip().split("#", 1)[0]
            if not target or re.match(r"^(?:https?://|mailto:)", target):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                ERRORS.append(f"broken local link in {relative}: {raw_target}")


def validate_placeholders() -> None:
    for path, relative in iter_runtime_files():
        if not path.is_file() or path.suffix.lower() not in {".md", ".yaml", ".yml", ".py"}:
            continue
        if "[" + "TODO" in path.read_text(encoding="utf-8"):
            ERRORS.append(f"template placeholder in {relative}")


def main() -> int:
    validate_frontmatter()
    validate_skill_budget()
    validate_inventory()
    validate_routes_and_regressions()
    validate_runtime_boundaries()
    validate_markdown_links()
    validate_placeholders()
    total = validate_upload_budget()

    if ERRORS:
        print(f"FAIL: {len(ERRORS)} problem(s)")
        for error in ERRORS:
            print(f"  - {error}")
        return 1
    print(f"OK: relationship-mentor skill structure is valid "
          f"({total / 1048576:.1f} MB shippable, all files < {MAX_SHIPPED_FILE_MB}MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
