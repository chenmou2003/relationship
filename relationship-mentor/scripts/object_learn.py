#!/usr/bin/env python3
"""Per-object learning store.

Archive chat logs the user hands over, distil a behavioural profile of the
counterpart, and accumulate a playbook of what has actually been verified to
work (or fail) on *that specific person*.

Local only: the database lives next to memory_store.py in the OS application
data directory (override with RELATIONSHIP_MENTOR_MEMORY_DIR), never inside the
repo, so archives are never pushed to git.

Usage:
    python scripts/object_learn.py ingest --subject A --file chat.txt [--me 张三] [--note "..."]
    python scripts/object_learn.py note --subject A --field 职业 --value "护士，轮班"
    python scripts/object_learn.py outcome --subject A --method "周三晚直接邀约" --verdict 有效
    python scripts/object_learn.py profile --subject A
    python scripts/object_learn.py brief --subject A --goal "约出来"
    python scripts/object_learn.py list
    python scripts/object_learn.py forget --subject A --confirm
    python scripts/object_learn.py purge --confirm
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MAX_TEXT = 2000
MAX_FIELD = 64
MAX_METHOD = 200
MAX_ARCHIVES_PER_OBJECT = 30
MAX_OBSERVATIONS_PER_OBJECT = 60
MAX_PLAYBOOK_PER_OBJECT = 40
VERDICTS = {"有效", "无效", "待验证"}

ME_ALIASES = {"我", "me", "ME", "自己", "本人", "我:", "用户"}

TIME_PATTERN = (
    r"(?:\[?\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?\]?"
    r"|\d{1,2}:\d{2}(?::\d{2})?)"
)
LINE_RE = re.compile(
    r"^\s*(?:" + TIME_PATTERN + r"\s*)?(?P<who>[^\s:：][^:：\n]{0,15}?)\s*[:：]\s?(?P<msg>.*)$"
)
STAMP_RE = re.compile(
    r"(?P<d>\d{4}[-/]\d{1,2}[-/]\d{1,2})?[ T]?(?P<t>\d{1,2}:\d{2}(?::\d{2})?)"
)

QUESTION_MARKERS = ("?", "？", "吗", "呢", "什么", "怎么", "为何", "为什么", "为啥", "哪个", "多久")
AVOID_MARKERS = ("忙", "再说", "下次", "改天", "看情况", "睡了", "有空再", "以后吧", "随便")
WARMTH_MARKERS = ("哈", "呀", "啦", "诶", "嘞", "~", "～", "😄", "😂", "😊", "🥰", "😆", "☺")
PLAN_MARKERS = ("周末", "周几", "明天", "后天", "一起", "见面", "出来", "吃饭", "电影", "下次", "有空", "去哪")


class LearnError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def data_dir() -> Path:
    override = os.environ.get("RELATIONSHIP_MENTOR_MEMORY_DIR") or os.environ.get(
        "GOUTOUJUNSHI_MEMORY_DIR"
    )
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "relationship-mentor"
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "relationship-mentor"
    base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    return base / "relationship-mentor"


def db_path() -> Path:
    return data_dir() / "objects.sqlite3"


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def connect() -> sqlite3.Connection:
    target = db_path()
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        target.parent.chmod(0o700)
    except OSError:
        pass
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS objects (
            subject_id TEXT PRIMARY KEY,
            alias TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS archives (
            id TEXT PRIMARY KEY,
            subject_id TEXT NOT NULL,
            source_ref TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '',
            provided_at TEXT NOT NULL,
            msg_me INTEGER NOT NULL DEFAULT 0,
            msg_obj INTEGER NOT NULL DEFAULT 0,
            chars_me INTEGER NOT NULL DEFAULT 0,
            chars_obj INTEGER NOT NULL DEFAULT 0,
            short_reply_rate REAL,
            question_rate REAL,
            expand_rate REAL,
            avoid_count INTEGER NOT NULL DEFAULT 0,
            unanswered_streaks INTEGER NOT NULL DEFAULT 0,
            obj_initiative INTEGER NOT NULL DEFAULT 0,
            avg_reply_minutes REAL,
            last_speaker TEXT NOT NULL DEFAULT '',
            engagement TEXT NOT NULL DEFAULT '',
            engagement_basis TEXT NOT NULL DEFAULT '',
            samples TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_archives_subject ON archives(subject_id, provided_at);
        CREATE TABLE IF NOT EXISTS observations (
            id TEXT PRIMARY KEY,
            subject_id TEXT NOT NULL,
            field TEXT NOT NULL,
            value TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'user_report',
            confidence TEXT NOT NULL DEFAULT 'medium',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_obs_subject ON observations(subject_id, created_at);
        CREATE TABLE IF NOT EXISTS playbook (
            id TEXT PRIMARY KEY,
            subject_id TEXT NOT NULL,
            method TEXT NOT NULL,
            verdict TEXT NOT NULL,
            context TEXT NOT NULL DEFAULT '',
            evidence TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_play_subject ON playbook(subject_id, updated_at);
        """
    )
    conn.commit()
    try:
        target.chmod(0o600)
    except OSError:
        pass
    return conn


def clean(value: Any, limit: int, name: str, required: bool = True) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise LearnError("INVALID_INPUT", f"{name} 必须是字符串")
    value = value.strip()
    if required and not value:
        raise LearnError("INVALID_INPUT", f"{name} 不能为空")
    if len(value) > limit:
        raise LearnError("INVALID_INPUT", f"{name} 超过 {limit} 字符")
    return value


def touch_object(conn: sqlite3.Connection, subject_id: str) -> None:
    stamp = now_iso()
    conn.execute(
        "INSERT INTO objects(subject_id, created_at, updated_at) VALUES(?, ?, ?) "
        "ON CONFLICT(subject_id) DO UPDATE SET updated_at = excluded.updated_at",
        (subject_id, stamp, stamp),
    )


def prune(
    conn: sqlite3.Connection, table: str, subject_id: str, limit: int, column: str
) -> None:
    conn.execute(
        f"DELETE FROM {table} WHERE subject_id = ? AND id NOT IN ("
        f"SELECT id FROM {table} WHERE subject_id = ? ORDER BY {column} DESC LIMIT ?)",
        (subject_id, subject_id, limit),
    )


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #


def parse_minutes(stamp: str) -> float | None:
    match = STAMP_RE.search(stamp)
    if not match or not match.group("t"):
        return None
    parts = [int(piece) for piece in match.group("t").split(":")]
    minutes = parts[0] * 60 + parts[1]
    if match.group("d"):
        date = re.split(r"[-/]", match.group("d"))
        minutes += int(date[0]) * 100000 + int(date[1]) * 1000 + int(date[2]) * 10
    return float(minutes)


def parse_transcript(raw: str, me_alias: str | None) -> tuple[list[tuple[str, str, float | None]], list[str]]:
    """Return [(speaker, message, minutes_or_None)] plus unparsed speakers seen."""
    messages: list[tuple[str, str, float | None]] = []
    speakers: list[str] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        stamp_match = re.match(r"^\s*(" + TIME_PATTERN + r")\s*(?=\S)", line)
        stamp = parse_minutes(stamp_match.group(1)) if stamp_match else None
        match = LINE_RE.match(line)
        if not match:
            if messages:
                who, text, prev = messages[-1]
                messages[-1] = (who, (text + " " + line.strip()).strip(), prev or stamp)
            continue
        who = match.group("who").strip().strip("[]（）()")
        text = match.group("msg").strip()
        if not who or len(who) > 20:
            continue
        messages.append((who, text, stamp))
        if who not in speakers:
            speakers.append(who)
    return messages, speakers


def split_sides(
    messages: list[tuple[str, str, float | None]], me_alias: str | None
) -> tuple[str, str] | None:
    """Decide which speaker is the user. Returns (me, object) or None if unclear."""
    counts: dict[str, int] = {}
    for who, _, _ in messages:
        counts[who] = counts.get(who, 0) + 1
    if me_alias:
        if me_alias not in counts:
            raise LearnError("SPEAKER_NOT_FOUND", f"记录里找不到说话人 {me_alias!r}")
        others = [who for who in counts if who != me_alias]
        if len(others) != 1:
            raise LearnError(
                "SPEAKER_AMBIGUOUS",
                "记录里有多个其他说话人，请用 --me 指定你自己，并把无关对象剔除",
            )
        return me_alias, others[0]
    for who in counts:
        if who.lower() in ME_ALIASES or who in ME_ALIASES:
            others = [name for name in counts if name != who]
            if len(others) == 1:
                return who, others[0]
    return None


def analyse(messages: list[tuple[str, str, float | None]], me: str, obj: str) -> dict[str, Any]:
    me_msgs = [text for who, text, _ in messages if who == me and text]
    obj_msgs = [text for who, text, _ in messages if who == obj and text]
    if not obj_msgs:
        raise LearnError("NO_OBJECT_MESSAGES", "没有解析到对方的发言，请检查记录格式或 --me 参数")

    def has(text: str, markers: tuple[str, ...]) -> bool:
        return any(marker in text for marker in markers)

    short = sum(1 for text in obj_msgs if len(text) <= 4 and not has(text, QUESTION_MARKERS))
    questions = sum(1 for text in obj_msgs if has(text, QUESTION_MARKERS))
    expanded = sum(1 for text in obj_msgs if len(text) >= 15)
    avoid = sum(1 for text in obj_msgs if has(text, AVOID_MARKERS))
    warmth = sum(1 for text in obj_msgs if has(text, WARMTH_MARKERS))
    plans = sum(1 for text in obj_msgs if has(text, PLAN_MARKERS))

    streaks = 0
    run = 0
    initiative = 0
    previous = ""
    for who, text, _ in messages:
        if not text:
            continue
        if who == me:
            run += 1
            if run >= 2:
                streaks += 1
                run = 0
        else:
            if previous == obj:
                initiative += 1
            run = 0
        previous = who

    latencies: list[float] = []
    pending: float | None = None
    for who, text, stamp in messages:
        if not text:
            continue
        if who == me:
            pending = stamp
            continue
        if who == obj and pending is not None and stamp is not None:
            delta = stamp - pending
            if 0 <= delta < 720:
                latencies.append(delta)
            pending = None

    total_obj = len(obj_msgs)
    short_rate = short / total_obj
    question_rate = questions / total_obj
    expand_rate = expanded / total_obj

    basis: list[str] = []
    if short_rate >= 0.5:
        basis.append(f"极简回复占 {short_rate:.0%}")
    if question_rate <= 0.1:
        basis.append(f"几乎不提问（{question_rate:.0%}）")
    if avoid >= 3:
        basis.append(f"回避/推迟措辞 {avoid} 次")
    if streaks >= 2:
        basis.append(f"我方连续发言未被接住 {streaks} 次")
    if question_rate >= 0.3:
        basis.append(f"主动提问 {question_rate:.0%}")
    if expand_rate >= 0.4:
        basis.append(f"有展开的长回复 {expand_rate:.0%}")
    if warmth:
        basis.append(f"正向语气标记 {warmth} 次")
    if plans:
        basis.append(f"提到见面/时间 {plans} 次")

    negative = (short_rate >= 0.5) or (question_rate <= 0.1) or avoid >= 3 or streaks >= 2
    positive = (question_rate >= 0.3 or expand_rate >= 0.4) and short_rate < 0.4
    if positive and not negative:
        engagement = "高"
    elif negative and not positive:
        engagement = "低"
    elif negative and positive:
        engagement = "中（信号混杂）"
    else:
        engagement = "中"

    return {
        "msg_me": len(me_msgs),
        "msg_obj": total_obj,
        "chars_me": sum(len(t) for t in me_msgs),
        "chars_obj": sum(len(t) for t in obj_msgs),
        "short_reply_rate": round(short_rate, 3),
        "question_rate": round(question_rate, 3),
        "expand_rate": round(expand_rate, 3),
        "avoid_count": avoid,
        "warmth_count": warmth,
        "plan_count": plans,
        "unanswered_streaks": streaks,
        "obj_initiative": initiative,
        "avg_reply_minutes": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "last_speaker": messages[-1][0] if messages else "",
        "engagement": engagement,
        "engagement_basis": "；".join(basis) or "样本太少，暂无稳定信号",
        "samples": json.dumps(
            {
                "敷衍样例": [t for t in obj_msgs if len(t) <= 4][:3],
                "积极样例": [t for t in obj_msgs if has(t, QUESTION_MARKERS) or len(t) >= 15][:3],
            },
            ensure_ascii=False,
        ),
    }


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #


def command_ingest(args: argparse.Namespace) -> None:
    subject = clean(args.subject, MAX_FIELD, "subject")
    source = clean(
        args.file or args.source_ref or "", MAX_TEXT, "source_ref", required=False
    )
    if getattr(args, "text", None):
        raw = args.text
    elif args.file:
        path = Path(args.file).expanduser()
        if not path.is_file():
            raise LearnError("FILE_NOT_FOUND", f"找不到文件: {path}")
        raw = path.read_text(encoding="utf-8", errors="replace")
    else:
        raw = sys.stdin.read()
    if len(raw.strip()) < 10:
        raise LearnError("EMPTY_INPUT", "对话记录太短，无法分析")

    messages, speakers = parse_transcript(raw, args.me)
    if len(messages) < 4:
        raise LearnError(
            "UNPARSED",
            "没能解析出足够的对话行。支持的格式：`名字: 内容` 或 `2026-09-14 21:03 名字: 内容`，一行一条",
        )
    sides = split_sides(messages, args.me)
    if sides is None:
        raise LearnError(
            "SPEAKER_AMBIGUOUS",
            f"认不出哪个是你。记录里的说话人：{speakers}。用 --me 你的名字 指定",
        )
    me, obj = sides
    metrics = analyse(messages, me, obj)

    with connect() as conn:
        touch_object(conn, subject)
        if args.alias:
            conn.execute(
                "UPDATE objects SET alias = ? WHERE subject_id = ?", (args.alias, subject)
            )
        conn.execute(
            """
            INSERT INTO archives(id, subject_id, source_ref, note, provided_at, msg_me,
                msg_obj, chars_me, chars_obj, short_reply_rate, question_rate, expand_rate,
                avoid_count, unanswered_streaks, obj_initiative, avg_reply_minutes,
                last_speaker, engagement, engagement_basis, samples)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                uuid.uuid4().hex,
                subject,
                source,
                clean(args.note, MAX_TEXT, "note", required=False),
                now_iso(),
                metrics["msg_me"],
                metrics["msg_obj"],
                metrics["chars_me"],
                metrics["chars_obj"],
                metrics["short_reply_rate"],
                metrics["question_rate"],
                metrics["expand_rate"],
                metrics["avoid_count"],
                metrics["unanswered_streaks"],
                metrics["obj_initiative"],
                metrics["avg_reply_minutes"],
                metrics["last_speaker"],
                metrics["engagement"],
                metrics["engagement_basis"],
                metrics["samples"],
            ),
        )
        for field, value in (
            ("最近投入度", f"{metrics['engagement']}（{metrics['engagement_basis']}）"),
            ("平均回复字数", f"{metrics['chars_obj'] / max(metrics['msg_obj'], 1):.1f} 字"),
            (
                "字数对比",
                f"我 {metrics['chars_me'] / max(metrics['msg_me'], 1):.1f} 字 / 对方 "
                f"{metrics['chars_obj'] / max(metrics['msg_obj'], 1):.1f} 字",
            ),
        ):
            conn.execute(
                "INSERT INTO observations(id, subject_id, field, value, source, confidence, created_at) "
                "VALUES(?,?,?,?,'archive','medium',?)",
                (uuid.uuid4().hex, subject, field, value, now_iso()),
            )
        prune(conn, "archives", subject, MAX_ARCHIVES_PER_OBJECT, "provided_at")
        prune(conn, "observations", subject, MAX_OBSERVATIONS_PER_OBJECT, "created_at")
        conn.commit()

    return (
        {
            "ok": True,
            "subject_id": subject,
            "speakers": {"me": me, "object": obj},
            "parsed_messages": len(messages),
            "metrics": metrics,
            "caveat": "以上仅为可见原文的文本行为指标，不等于对方的内心状态",
        }
    )


def command_note(args: argparse.Namespace) -> None:
    subject = clean(args.subject, MAX_FIELD, "subject")
    with connect() as conn:
        touch_object(conn, subject)
        conn.execute(
            "INSERT INTO observations(id, subject_id, field, value, source, confidence, created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (
                uuid.uuid4().hex,
                subject,
                clean(args.field, MAX_FIELD, "field"),
                clean(args.value, MAX_TEXT, "value"),
                args.source,
                args.confidence,
                now_iso(),
            ),
        )
        prune(conn, "observations", subject, MAX_OBSERVATIONS_PER_OBJECT, "created_at")
        conn.commit()
    return {"ok": True, "subject_id": subject}


def command_outcome(args: argparse.Namespace) -> None:
    subject = clean(args.subject, MAX_FIELD, "subject")
    method = clean(args.method, MAX_METHOD, "method")
    if args.verdict not in VERDICTS:
        raise LearnError("INVALID_VERDICT", f"verdict 必须是 {sorted(VERDICTS)} 之一")
    with connect() as conn:
        touch_object(conn, subject)
        existing = conn.execute(
            "SELECT * FROM playbook WHERE subject_id = ? AND method = ?",
            (subject, method),
        ).fetchone()
        stamp = now_iso()
        evidence = clean(args.evidence, MAX_TEXT, "evidence", required=False)
        context = clean(args.context, MAX_TEXT, "context", required=False)
        if existing:
            conn.execute(
                "UPDATE playbook SET verdict = ?, context = COALESCE(NULLIF(?,''), context), "
                "evidence = COALESCE(NULLIF(?,''), evidence), updated_at = ? WHERE id = ?",
                (args.verdict, context, evidence, stamp, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO playbook(id, subject_id, method, verdict, context, evidence, "
                "created_at, updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, subject, method, args.verdict, context, evidence, stamp, stamp),
            )
        prune(conn, "playbook", subject, MAX_PLAYBOOK_PER_OBJECT, "updated_at")
        conn.commit()
    return {"ok": True, "subject_id": subject, "method": method, "verdict": args.verdict}


def gather(conn: sqlite3.Connection, subject_id: str) -> dict[str, Any]:
    obj_row = conn.execute(
        "SELECT * FROM objects WHERE subject_id = ?", (subject_id,)
    ).fetchone()
    if not obj_row:
        raise LearnError("NOT_FOUND", f"没有对象 {subject_id} 的档案，先用 ingest 或 note 建一个")
    archives = [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM archives WHERE subject_id = ? ORDER BY provided_at DESC",
            (subject_id,),
        )
    ]
    observations = [
        dict(row)
        for row in conn.execute(
            "SELECT field, value, source, confidence, created_at FROM observations "
            "WHERE subject_id = ? ORDER BY created_at DESC",
            (subject_id,),
        )
    ]
    playbook = [
        dict(row)
        for row in conn.execute(
            "SELECT method, verdict, context, evidence, updated_at FROM playbook "
            "WHERE subject_id = ? ORDER BY updated_at DESC",
            (subject_id,),
        )
    ]
    return {"object": dict(obj_row), "archives": archives, "observations": observations, "playbook": playbook}


def summarise(data: dict[str, Any]) -> dict[str, Any]:
    archives = data["archives"]
    latest = archives[0] if archives else None
    trend = [row["engagement"] for row in archives[:6]]
    worked = [row["method"] for row in data["playbook"] if row["verdict"] == "有效"]
    failed = [row["method"] for row in data["playbook"] if row["verdict"] == "无效"]
    pending = [row["method"] for row in data["playbook"] if row["verdict"] == "待验证"]
    return {
        "subject_id": data["object"]["subject_id"],
        "alias": data["object"]["alias"],
        "archived_sessions": len(archives),
        "latest_engagement": latest["engagement"] if latest else "",
        "engagement_trend_newest_first": trend,
        "latest_basis": latest["engagement_basis"] if latest else "",
        "avg_reply_minutes": latest["avg_reply_minutes"] if latest else None,
        "observations": data["observations"][:12],
        "playbook": {"已验证有效": worked, "已验证无效": failed, "待验证": pending},
        "confidence": "样本越多越准" if len(archives) >= 3 else "样本不足 3 次，结论只能当参考",
    }


def command_profile(args: argparse.Namespace) -> None:
    subject = clean(args.subject, MAX_FIELD, "subject")
    with connect() as conn:
        data = gather(conn, subject)
    return {"ok": True, "summary": summarise(data), "archives": data["archives"]}


def command_brief(args: argparse.Namespace) -> None:
    """Compact context block for the agent, plus corpus keywords to look up."""
    subject = clean(args.subject, MAX_FIELD, "subject")
    goal = clean(args.goal, MAX_TEXT, "goal", required=False)
    with connect() as conn:
        data = gather(conn, subject)
    summary = summarise(data)
    keywords = [goal] if goal else []
    latest = data["archives"][0] if data["archives"] else None
    if latest:
        if latest["short_reply_rate"] and latest["short_reply_rate"] >= 0.5:
            keywords += ["回应冷淡", "已读不回", "聊天聊死"]
        if latest["avoid_count"] >= 3:
            keywords += ["邀约被拒", "窗口判断"]
        if latest["unanswered_streaks"] >= 2:
            keywords += ["需求感", "停止纠缠"]
        if latest["question_rate"] and latest["question_rate"] >= 0.3:
            keywords += ["关系升级", "收尾邀约"]
    playbook = data["playbook"]
    return (
        {
            "ok": True,
            "profile": summary,
            "verified_effective": [row for row in playbook if row["verdict"] == "有效"],
            "verified_failed": [row for row in playbook if row["verdict"] == "无效"],
            "suggested_corpus_keywords": keywords[:6],
            "next_step": "拿上面的关键词跑 scripts/query.py，再结合已验证有效/无效给方案",
            "caveat": "档案只来自用户提供的记录与陈述，不得外推为对方的人格或动机",
        }
    )


def command_list(_: argparse.Namespace) -> None:
    with connect() as conn:
        rows = [
            {
                "subject_id": row["subject_id"],
                "alias": row["alias"],
                "updated_at": row["updated_at"],
                "archives": conn.execute(
                    "SELECT COUNT(*) AS n FROM archives WHERE subject_id = ?",
                    (row["subject_id"],),
                ).fetchone()["n"],
                "playbook": conn.execute(
                    "SELECT COUNT(*) AS n FROM playbook WHERE subject_id = ?",
                    (row["subject_id"],),
                ).fetchone()["n"],
            }
            for row in conn.execute("SELECT * FROM objects ORDER BY updated_at DESC")
        ]
    return {"count": len(rows), "objects": rows}


def command_forget(args: argparse.Namespace) -> None:
    if not args.confirm:
        raise LearnError("CONFIRMATION_REQUIRED", "需要 --confirm 才会永久删除该对象档案")
    subject = clean(args.subject, MAX_FIELD, "subject")
    with connect() as conn:
        conn.execute("DELETE FROM archives WHERE subject_id = ?", (subject,))
        conn.execute("DELETE FROM observations WHERE subject_id = ?", (subject,))
        conn.execute("DELETE FROM playbook WHERE subject_id = ?", (subject,))
        conn.execute("DELETE FROM objects WHERE subject_id = ?", (subject,))
        conn.commit()
        conn.execute("VACUUM")
    return {"ok": True, "deleted": subject}


def command_purge(args: argparse.Namespace) -> None:
    if not args.confirm:
        raise LearnError("CONFIRMATION_REQUIRED", "需要 --confirm 才会清空全部学习档案")
    target = db_path()
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(target) + suffix)
        if candidate.exists():
            candidate.unlink()
    return {"ok": True, "purged": str(target)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="归档一段对话记录并抽取行为指标")
    ingest.add_argument("--subject", required=True, help="对象代号，如 A")
    ingest.add_argument("--file", help="对话记录文件路径")
    ingest.add_argument("--text", help="对话记录正文（与 --file 二选一，供 MCP 等程序调用）")
    ingest.add_argument("--source-ref", help="来源说明，如 微信导出/手打")
    ingest.add_argument("--me", help="记录里代表你自己的名字")
    ingest.add_argument("--alias", help="给对象起个备注名")
    ingest.add_argument("--note", default="", help="这段记录的背景")
    ingest.set_defaults(func=command_ingest)

    note = sub.add_parser("note", help="手写一条关于对象的观察")
    note.add_argument("--subject", required=True)
    note.add_argument("--field", required=True, help="如 职业 / 作息 / 雷区 / 喜好")
    note.add_argument("--value", required=True)
    note.add_argument("--source", default="user_report")
    note.add_argument("--confidence", default="medium", choices=["high", "medium", "low"])
    note.set_defaults(func=command_note)

    outcome = sub.add_parser("outcome", help="记录某个做法对这个对象的实际效果")
    outcome.add_argument("--subject", required=True)
    outcome.add_argument("--method", required=True)
    outcome.add_argument("--verdict", required=True, choices=sorted(VERDICTS))
    outcome.add_argument("--context", default="")
    outcome.add_argument("--evidence", default="", help="对方的原话或具体反应")
    outcome.set_defaults(func=command_outcome)

    profile = sub.add_parser("profile", help="输出对象画像")
    profile.add_argument("--subject", required=True)
    profile.set_defaults(func=command_profile)

    brief = sub.add_parser("brief", help="给 agent 用的紧凑上下文 + 建议检索关键词")
    brief.add_argument("--subject", required=True)
    brief.add_argument("--goal", default="")
    brief.set_defaults(func=command_brief)

    sub.add_parser("list").set_defaults(func=command_list)

    forget = sub.add_parser("forget")
    forget.add_argument("--subject", required=True)
    forget.add_argument("--confirm", action="store_true")
    forget.set_defaults(func=command_forget)

    purge = sub.add_parser("purge")
    purge.add_argument("--confirm", action="store_true")
    purge.set_defaults(func=command_purge)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        emit(args.func(args))
        return 0
    except (LearnError, json.JSONDecodeError, OSError, sqlite3.Error) as exc:
        code = exc.code if isinstance(exc, LearnError) else exc.__class__.__name__.upper()
        emit({"ok": False, "error": {"code": code, "message": str(exc)}})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
