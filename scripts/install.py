#!/usr/bin/env python3
"""Install this skill into the skill directory of any supported agent.

Zero third-party dependencies. Copying (not symlinking) keeps things working
for clients that refuse to follow symlinks.

Usage:
    python3 scripts/install.py                       # detect agents + install status
    python3 scripts/install.py --install claude      # install into one agent
    python3 scripts/install.py --install all         # install into every detected agent
    python3 scripts/install.py --uninstall claude    # remove again
    python3 scripts/install.py --print-mcp           # print MCP config with real paths
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "relationship-mentor"

# target name -> directory that must exist for the agent to be considered present
TARGETS: dict[str, tuple[str, Path]] = {
    "workbuddy": ("WorkBuddy", Path.home() / ".workbuddy" / "skills"),
    "claude": ("Claude Code / Claude.ai skills", Path.home() / ".claude" / "skills"),
    "codex": ("Codex CLI", Path.home() / ".codex" / "skills"),
    "cursor": ("Cursor", Path.home() / ".cursor" / "skills"),
    "gemini": ("Gemini CLI / Antigravity", Path.home() / ".gemini" / "skills"),
    "opencode": ("OpenCode", Path.home() / ".config" / "opencode" / "skills"),
}

IGNORE = shutil.ignore_patterns(
    ".backup", ".git", ".workbuddy", "__pycache__", ".DS_Store", "*.pyc", "*.pyo"
)


def detect() -> dict[str, dict[str, object]]:
    report: dict[str, dict[str, object]] = {}
    for key, (label, base) in TARGETS.items():
        destination = base / SKILL_NAME
        report[key] = {
            "label": label,
            "base_exists": base.exists(),
            "path": str(destination),
            "installed": destination.exists(),
        }
    return report


def print_report(report: dict[str, dict[str, object]]) -> None:
    print("检测到的 agent 技能目录：\n")
    for key, info in report.items():
        state = "已安装" if info["installed"] else ("可用" if info["base_exists"] else "未检测到")
        print(f"  [{key:9s}] {state:6s}  {info['label']}")
        print(f"              {info['path']}")
    print()


def install(key: str, dry_run: bool = False) -> bool:
    label, base = TARGETS[key]
    destination = base / SKILL_NAME
    if dry_run:
        print(f"[dry-run] 将安装到 {destination}")
        return True
    if not base.exists():
        print(f"跳过 {label}：目录不存在 {base}")
        return False
    if destination.exists():
        shutil.rmtree(destination)
    base.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT, destination, ignore=IGNORE, symlinks=False)
    print(f"已安装 {label} -> {destination}")
    return True


def uninstall(key: str) -> bool:
    label, base = TARGETS[key]
    destination = base / SKILL_NAME
    if not destination.exists():
        print(f"未安装：{destination}")
        return False
    shutil.rmtree(destination)
    print(f"已卸载 {label} -> {destination}")
    return True


def print_mcp() -> None:
    config = {
        "mcpServers": {
            SKILL_NAME: {
                "command": "python3",
                "args": [str(ROOT / "scripts" / "mcp_server.py")],
            }
        }
    }
    print(json.dumps(config, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--install", metavar="TARGET", nargs="+", help=f"目标: {', '.join(TARGETS)} 或 all")
    parser.add_argument("--uninstall", metavar="TARGET", nargs="+")
    parser.add_argument("--print-mcp", action="store_true", help="输出可直接粘贴的 MCP 配置")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.print_mcp:
        print_mcp()
        return 0

    report = detect()
    print_report(report)

    if args.uninstall:
        keys = list(TARGETS) if "all" in args.uninstall else args.uninstall
        for key in keys:
            if key not in TARGETS:
                print(f"未知目标: {key}")
                continue
            uninstall(key)
        return 0

    if args.install:
        keys = list(TARGETS) if "all" in args.install else args.install
        installed = 0
        for key in keys:
            if key not in TARGETS:
                print(f"未知目标: {key}")
                continue
            if install(key, args.dry_run):
                installed += 1
        print(f"\n完成 {installed} 个目标。")
        if installed:
            print("MCP 方式（免复制、任意客户端）配置：python3 scripts/install.py --print-mcp")
        return 0

    print("安装：python3 scripts/install.py --install claude")
    print("     python3 scripts/install.py --install all")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
