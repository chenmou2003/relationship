#!/usr/bin/env python3
"""MCP server for relationship-mentor — stdio transport, zero third-party deps.

Lets any MCP-capable client (Claude Desktop, Claude Code, Cursor, Windsurf,
Cherry Studio, Dify, Coze, ...) drive the corpus and the object-learning store
without knowing anything about this repo's layout.

    python scripts/mcp_server.py

Config snippet (see mcp.example.json):

    {"mcpServers": {"relationship-mentor": {
        "command": "python3",
        "args": ["/absolute/path/to/relationship-mentor/scripts/mcp_server.py"]}}}

Nothing except JSON-RPC may touch stdout; diagnostics go to stderr.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import object_learn  # noqa: E402  (sibling module; path fixed above)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
QUERY = HERE / "query.py"
PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "relationship-mentor"
SERVER_VERSION = "3.1.0"

INSTRUCTIONS = (
    "情感导师知识库。给出任何情感/恋爱/沟通方面的判断、方法或话术之前，"
    "必须先调用 corpus_* 工具检索并引用来源（技法/话术/案例/原文 #id），没检索就回答等于编。"
    "涉及已建档对象时先调 object_brief，拿到画像与已验证有效/无效清单后再给方案。"
)


# --------------------------------------------------------------------------- #
# Corpus tools: delegate to query.py so behaviour can never drift.
# --------------------------------------------------------------------------- #


def run_query(args: list[str]) -> str:
    if not QUERY.is_file():
        raise RuntimeError(f"找不到检索脚本: {QUERY}")
    proc = subprocess.run(
        [sys.executable, str(QUERY), *args],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    output = (proc.stdout or "").strip()
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "query.py 执行失败").strip())
    return output or "（无结果）"


def tool_corpus_search(query: str, limit: int = 5) -> str:
    return run_query(["search", query, "-n", str(limit)])


def tool_corpus_concept(query: str, limit: int = 5) -> str:
    return run_query(["concept", query, "-n", str(limit)])


def tool_corpus_tech(query: str, limit: int = 5) -> str:
    return run_query(["tech", query, "-n", str(limit)])


def tool_corpus_script(query: str, limit: int = 5) -> str:
    return run_query(["script", query, "-n", str(limit)])


def tool_corpus_case(query: str, limit: int = 5) -> str:
    return run_query(["case", query, "-n", str(limit)])


def tool_corpus_principle(query: str, limit: int = 5) -> str:
    return run_query(["principle", query, "-n", str(limit)])


def tool_corpus_read(doc_id: str) -> str:
    return run_query(["read", str(doc_id)])


def tool_corpus_stats() -> str:
    return run_query(["stats"])


# --------------------------------------------------------------------------- #
# Object-learning tools: call object_learn in-process (its commands return dicts).
# --------------------------------------------------------------------------- #


def _namespace(**kwargs: Any) -> argparse.Namespace:
    return argparse.Namespace(**kwargs)


def tool_object_ingest(
    subject: str,
    text: str,
    me: str = "",
    alias: str = "",
    note: str = "",
    source_ref: str = "",
) -> str:
    args = _namespace(
        subject=subject,
        text=text,
        file=None,
        me=me or None,
        alias=alias or None,
        note=note,
        source_ref=source_ref,
    )
    return json.dumps(object_learn.command_ingest(args), ensure_ascii=False, indent=2)


def tool_object_note(
    subject: str, field: str, value: str, source: str = "user_report", confidence: str = "medium"
) -> str:
    args = _namespace(subject=subject, field=field, value=value, source=source, confidence=confidence)
    return json.dumps(object_learn.command_note(args), ensure_ascii=False, indent=2)


def tool_object_outcome(
    subject: str, method: str, verdict: str, context: str = "", evidence: str = ""
) -> str:
    args = _namespace(
        subject=subject,
        method=method,
        verdict=verdict,
        context=context,
        evidence=evidence,
    )
    return json.dumps(object_learn.command_outcome(args), ensure_ascii=False, indent=2)


def tool_object_brief(subject: str, goal: str = "") -> str:
    args = _namespace(subject=subject, goal=goal)
    return json.dumps(object_learn.command_brief(args), ensure_ascii=False, indent=2)


def tool_object_profile(subject: str) -> str:
    args = _namespace(subject=subject)
    return json.dumps(object_learn.command_profile(args), ensure_ascii=False, indent=2)


def tool_object_list() -> str:
    return json.dumps(object_learn.command_list(_namespace()), ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------- #
# Tool catalogue
# --------------------------------------------------------------------------- #


def _kw(desc: str) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "关键词；多个词用空格分隔"},
            "limit": {"type": "integer", "description": "返回条数，默认 5", "default": 5},
        },
        "required": ["query"],
    }


TOOLS: list[dict[str, Any]] = [
    {
        "name": "corpus_search",
        "description": "全文检索 1637 篇情感语料原文，返回标题、命中次数与上下文片段。多词用空格分隔。",
        "inputSchema": _kw("搜索关键词"),
    },
    {
        "name": "corpus_tech",
        "description": "查技法库（277 条），返回场景/步骤/坑/来源。",
        "inputSchema": _kw("技法关键词，如 邀约、聊天"),
    },
    {
        "name": "corpus_script",
        "description": "查话术库（273 条），返回场景/话术/用法。",
        "inputSchema": _kw("话术关键词，如 破冰、拒绝"),
    },
    {
        "name": "corpus_case",
        "description": "查真实咨询案例库（158 条），返回处境与教训。",
        "inputSchema": _kw("案例关键词，如 冷淡、分手"),
    },
    {
        "name": "corpus_concept",
        "description": "查概念库（292 条），返回定义与来源。",
        "inputSchema": _kw("概念关键词，如 需求感、框架"),
    },
    {
        "name": "corpus_principle",
        "description": "查原则库（329 条）。",
        "inputSchema": _kw("原则关键词，如 吸引力、边界"),
    },
    {
        "name": "corpus_read",
        "description": "按 id 读某篇语料原文（前 8000 字）。",
        "inputSchema": {
            "type": "object",
            "properties": {"doc_id": {"type": "string", "description": "原文 id，如 1417"}},
            "required": ["doc_id"],
        },
    },
    {
        "name": "corpus_stats",
        "description": "知识库统计：篇数、字数、各表条数、分类分布、数据库体积。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "object_brief",
        "description": (
            "取某个对话对象的画像：投入度与判定依据、观察、已验证有效/无效的做法、建议检索关键词。"
            "涉及已建档对象时，开场先调它。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "对象代号，如 A"},
                "goal": {"type": "string", "description": "这次想达成的目标，如 约出来"},
            },
            "required": ["subject"],
        },
    },
    {
        "name": "object_profile",
        "description": "取某个对象的完整画像与历次归档记录。",
        "inputSchema": {
            "type": "object",
            "properties": {"subject": {"type": "string"}},
            "required": ["subject"],
        },
    },
    {
        "name": "object_ingest",
        "description": (
            "归档一段对话记录并抽取行为指标（短回复率/提问率/展开率/回避措辞/连续未回应/"
            "平均回复间隔/投入度及依据）。格式：'名字: 内容' 或 '2026-09-14 21:03 名字: 内容'。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "对象代号"},
                "text": {"type": "string", "description": "对话记录全文"},
                "me": {"type": "string", "description": "记录里代表用户自己的名字"},
                "alias": {"type": "string", "description": "对象备注名"},
                "note": {"type": "string", "description": "这段记录的背景"},
                "source_ref": {"type": "string", "description": "来源说明"},
            },
            "required": ["subject", "text"],
        },
    },
    {
        "name": "object_note",
        "description": "手写一条关于对象的观察（职业/作息/喜好/雷区等）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "field": {"type": "string", "description": "如 职业、作息、雷区"},
                "value": {"type": "string"},
                "source": {"type": "string", "default": "user_report"},
                "confidence": {"type": "string", "default": "medium"},
            },
            "required": ["subject", "field", "value"],
        },
    },
    {
        "name": "object_outcome",
        "description": (
            "记录某个做法对这个对象的实际效果（有效/无效/待验证），并附对方原话作为证据。"
            "这是逐步定制化的引擎。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "method": {"type": "string", "description": "具体做法，如 用共同兴趣切入"},
                "verdict": {"type": "string", "description": "有效 / 无效 / 待验证"},
                "context": {"type": "string"},
                "evidence": {"type": "string", "description": "对方的原话或具体反应"},
            },
            "required": ["subject", "method", "verdict"],
        },
    },
    {
        "name": "object_list",
        "description": "列出所有已建档对象及其归档数、打法数。",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

HANDLERS = {
    "corpus_search": lambda a: tool_corpus_search(a["query"], int(a.get("limit", 5))),
    "corpus_tech": lambda a: tool_corpus_tech(a["query"], int(a.get("limit", 5))),
    "corpus_script": lambda a: tool_corpus_script(a["query"], int(a.get("limit", 5))),
    "corpus_case": lambda a: tool_corpus_case(a["query"], int(a.get("limit", 5))),
    "corpus_concept": lambda a: tool_corpus_concept(a["query"], int(a.get("limit", 5))),
    "corpus_principle": lambda a: tool_corpus_principle(a["query"], int(a.get("limit", 5))),
    "corpus_read": lambda a: tool_corpus_read(a["doc_id"]),
    "corpus_stats": lambda a: tool_corpus_stats(),
    "object_brief": lambda a: tool_object_brief(a["subject"], a.get("goal", "")),
    "object_profile": lambda a: tool_object_profile(a["subject"]),
    "object_ingest": lambda a: tool_object_ingest(
        a["subject"],
        a["text"],
        a.get("me", ""),
        a.get("alias", ""),
        a.get("note", ""),
        a.get("source_ref", ""),
    ),
    "object_note": lambda a: tool_object_note(
        a["subject"], a["field"], a["value"], a.get("source", "user_report"),
        a.get("confidence", "medium"),
    ),
    "object_outcome": lambda a: tool_object_outcome(
        a["subject"], a["method"], a["verdict"], a.get("context", ""), a.get("evidence", "")
    ),
    "object_list": lambda a: tool_object_list(),
}


PROMPTS = [
    {
        "name": "mentor-rules",
        "description": "情感导师的核心行为准则（查库优先、红线、工作流、对象学习）",
    }
]


def prompt_text() -> str:
    files = {
        "规范全文": ROOT / "AGENT.md",
        "精简系统提示": ROOT / "system_prompt.md",
    }
    parts = [INSTRUCTIONS, "", "完整规范见下列文件（用你的文件读取能力打开）："]
    for label, path in files.items():
        parts.append(f"- {label}: {path}")
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# JSON-RPC plumbing
# --------------------------------------------------------------------------- #


def ok(message_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def err(message_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": message}}


def handle_initialize(message_id: Any) -> dict[str, Any]:
    return ok(
        message_id,
        {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}, "prompts": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions": INSTRUCTIONS,
        },
    )


def handle_tools_call(message_id: Any, params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name", "")
    arguments = params.get("arguments") or {}
    handler = HANDLERS.get(name)
    if handler is None:
        return err(message_id, -32602, f"未知工具: {name}")
    schema = next((t["inputSchema"] for t in TOOLS if t["name"] == name), {})
    missing = [key for key in schema.get("required", []) if key not in arguments]
    if missing:
        return ok(
            message_id,
            {
                "content": [
                    {"type": "text", "text": f"{name} 缺少必填参数: {', '.join(missing)}"}
                ],
                "isError": True,
            },
        )
    try:
        text = handler(arguments)
        return ok(message_id, {"content": [{"type": "text", "text": text}], "isError": False})
    except Exception as exc:  # surfaced to the model, not the transport
        return ok(
            message_id,
            {"content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}], "isError": True},
        )


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    message_id = message.get("id")
    method = message.get("method", "")
    params = message.get("params") or {}

    if method in {"notifications/initialized", "notifications/cancelled"}:
        return None
    if method == "initialize":
        return handle_initialize(message_id)
    if method == "ping":
        return ok(message_id, {})
    if method == "tools/list":
        return ok(message_id, {"tools": TOOLS})
    if method == "tools/call":
        return handle_tools_call(message_id, params)
    if method == "prompts/list":
        return ok(message_id, {"prompts": PROMPTS})
    if method == "prompts/get":
        return ok(
            message_id,
            {
                "description": PROMPTS[0]["description"],
                "messages": [
                    {"role": "user", "content": {"type": "text", "text": prompt_text()}}
                ],
            },
        )
    if message_id is None:
        return None
    return err(message_id, -32601, f"不支持的方法: {method}")


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            print(f"忽略非法 JSON: {line[:120]}", file=sys.stderr)
            continue
        response = handle(message)
        if response is None:
            continue
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
