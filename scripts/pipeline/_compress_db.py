#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 mentor.db 压缩成可直传 GitHub 的体积（维护者专用，一次性/重建时用）。

做的事：
1. docs.content 用 zlib(level 9) 压缩成 BLOB（27.5MB -> 11.1MB）；
2. 不建 FTS5 索引（trigram 倒排占 63.5MB，改用 query.py 的 Python 端扫描，
   全库一次约 0.01s，完全够用）；
3. 保留全部结构化表与索引，最后 VACUUM。

产物体积约 12MB，低于 GitHub 网页上传的 25MB 单文件上限。
需要的亚秒级 FTS5 检索可在本地重建：见 scripts/build_fts.py。

用法：
    python scripts/pipeline/_compress_db.py [源db] [目标db]
默认：database/mentor.db -> database/mentor.db.compressed
"""
import os
import sqlite3
import sys
import zlib

TABLES_NO_DOCS = ("concepts", "techniques", "scripts", "cases", "principles", "topics", "doc_tokens")

DOCS_DDL = """
CREATE TABLE docs (
  id INTEGER PRIMARY KEY,
  seq INTEGER, filename TEXT, title TEXT, tier TEXT, tier_cn TEXT,
  chars INTEGER, clean_chars INTEGER, is_dup INTEGER DEFAULT 0,
  dup_of TEXT DEFAULT '', content BLOB
)
"""

OTHER_DDL = {
    "concepts": "CREATE TABLE concepts (id INTEGER PRIMARY KEY, name TEXT, def TEXT, source TEXT, batch TEXT)",
    "techniques": "CREATE TABLE techniques (id INTEGER PRIMARY KEY, name TEXT, stage TEXT, scenario TEXT, steps TEXT, pitfall TEXT, source TEXT, batch TEXT)",
    "scripts": "CREATE TABLE scripts (id INTEGER PRIMARY KEY, scene TEXT, line TEXT, usage TEXT, source TEXT, batch TEXT)",
    "cases": "CREATE TABLE cases (id INTEGER PRIMARY KEY, title TEXT, situation TEXT, lesson TEXT, source TEXT, batch TEXT)",
    "principles": "CREATE TABLE principles (id INTEGER PRIMARY KEY, text TEXT, source TEXT, batch TEXT)",
    "topics": "CREATE TABLE topics (id INTEGER PRIMARY KEY, topic TEXT, doc_id INTEGER, title TEXT, score INTEGER)",
    "doc_tokens": "CREATE TABLE doc_tokens (doc_id INTEGER PRIMARY KEY, title TEXT)",
}

INDEXES = (
    "CREATE INDEX idx_docs_tier ON docs(tier_cn)",
    "CREATE INDEX idx_docs_title ON docs(title)",
)


def copy_table(src: sqlite3.Connection, dst: sqlite3.Connection, table: str) -> int:
    rows = src.execute("SELECT * FROM %s" % table).fetchall()
    if not rows:
        return 0
    cols = [d[0] for d in src.execute("SELECT * FROM %s LIMIT 1" % table).description]
    placeholders = ",".join("?" * len(cols))
    dst.executemany(
        "INSERT INTO %s (%s) VALUES (%s)" % (table, ",".join(cols), placeholders), rows
    )
    return len(rows)


def main() -> int:
    src_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join("database", "mentor.db")
    dst_path = sys.argv[2] if len(sys.argv) > 2 else src_path + ".compressed"

    src = sqlite3.connect(src_path)
    src.row_factory = sqlite3.Row
    if os.path.exists(dst_path):
        os.remove(dst_path)
    dst = sqlite3.connect(dst_path)

    dst.execute(DOCS_DDL)
    for ddl in OTHER_DDL.values():
        dst.execute(ddl)

    print("复制 docs（content 压缩中）…")
    total = src.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
    done = 0
    for row in src.execute("SELECT * FROM docs"):
        content = row["content"] or ""
        dst.execute(
            "INSERT INTO docs (id, seq, filename, title, tier, tier_cn, chars, clean_chars,"
            " is_dup, dup_of, content) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                row["id"], row["seq"], row["filename"], row["title"], row["tier"],
                row["tier_cn"], row["chars"], row["clean_chars"], row["is_dup"],
                row["dup_of"], zlib.compress(content.encode("utf-8"), 9),
            ),
        )
        done += 1
        if done % 400 == 0:
            print("  %d/%d" % (done, total))

    for table in TABLES_NO_DOCS:
        try:
            n = copy_table(src, dst, table)
            print("  %-12s %d 条" % (table, n))
        except sqlite3.Error as exc:
            print("  跳过 %s：%s" % (table, exc))

    for ddl in INDEXES:
        dst.execute(ddl)
    dst.commit()
    print("VACUUM…")
    dst.execute("VACUUM")
    dst.close()
    src.close()

    before = os.path.getsize(src_path) / 1048576
    after = os.path.getsize(dst_path) / 1048576
    print("完成：%.1f MB -> %.1f MB（%.0f%%）" % (before, after, after / before * 100))
    print("输出：%s" % dst_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
