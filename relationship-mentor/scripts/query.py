#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""情感知识库检索工具（零第三方依赖，Python 3.8+）

语料全文以 zlib 压缩存储，本脚本透明解压；全文检索走 Python 端扫描，
全库 1637 篇约 0.01–0.9 秒，无需 FTS5 索引（省下 63MB）。

用法：
  python query.py search <关键词> [-n 条数]        全文检索原始语料（1637 篇 / 986 万字）
  python query.py concept <关键词> [-n 条数]       查炼化后的概念
  python query.py tech <关键词> [-n 条数]          查技法
  python query.py script <关键词> [-n 条数]        查话术
  python query.py case <关键词> [-n 条数]          查案例
  python query.py principle <关键词> [-n 条数]     查原则
  python query.py read <id>                        读取某篇原文
  python query.py stats                            库统计
"""
import os
import sys
import zlib
import sqlite3
import re
import argparse

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'database', 'mentor.db')
DB = os.path.normpath(DB)


def conn():
    if not os.path.exists(DB):
        sys.exit('找不到数据库：%s' % DB)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def decode(value):
    """content 可能是 zlib 压缩后的 BLOB，也可能是纯文本（兼容未压缩的库）。"""
    if value is None:
        return ''
    if isinstance(value, bytes):
        try:
            return zlib.decompress(value).decode('utf-8', 'replace')
        except zlib.error:
            return value.decode('utf-8', 'replace')
    return value


def snippet(text, kw, width=140):
    if not text:
        return ''
    terms = [t for t in re.split(r'\s+', kw) if t] or ['']
    pos = -1
    for t in terms:
        pos = text.find(t)
        if pos >= 0:
            break
    if pos < 0:
        return text[:width].replace('\n', ' ')
    s = max(0, pos - width // 3)
    return ('…' if s else '') + text[s:s + width].replace('\n', ' ')


def out(rows, fmt):
    if not rows:
        print('（无结果）')
        return
    for r in rows:
        print(fmt(r))


def cmd_search(c, kw, n):
    """全库扫描：按关键词出现次数排序。空格分隔多个词，任一命中即收录。"""
    terms = [t for t in re.split(r'\s+', kw.strip()) if t]
    if not terms:
        print('（请给出关键词）')
        return
    hits = []
    for r in c.execute("SELECT id, title, tier_cn, clean_chars, content FROM docs"):
        text = decode(r['content'])
        score = sum(text.count(t) for t in terms)
        if score:
            hits.append((score, r['id'], r['title'], r['tier_cn'], r['clean_chars'], text))
    # 命中次数相同时，短文档排在前面（关键词密度更高）
    hits.sort(key=lambda x: (-x[0], x[4] or 0))
    for score, doc_id, title, tier, chars, text in hits[:n]:
        print("[#%d][%s] %s  （命中 %d 次）" % (doc_id, tier, title, score))
        print("    %s\n" % snippet(text, kw))


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('cmd')
    ap.add_argument('kw', nargs='?', default='')
    ap.add_argument('-n', type=int, default=10)
    a = ap.parse_args()
    c = conn()

    if a.cmd == 'search':
        cmd_search(c, a.kw, a.n)

    elif a.cmd in ('concept', 'concepts'):
        rows = c.execute(
            "SELECT name, def, source FROM concepts WHERE name||def||source LIKE ? LIMIT ?",
            ('%' + a.kw + '%', a.n)).fetchall()
        out(rows, lambda r: "· %s：%s  〔%s〕" % (r['name'], r['def'], r['source']))

    elif a.cmd in ('tech', 'techniques'):
        rows = c.execute(
            "SELECT name, stage, scenario, steps, pitfall, source FROM techniques "
            "WHERE name||scenario||steps||stage LIKE ? LIMIT ?", ('%' + a.kw + '%', a.n)).fetchall()
        out(rows, lambda r: "▍%s 〔%s〕\n  场景：%s\n  步骤：%s\n  坑：%s  〔%s〕"
            % (r['name'], r['stage'], r['scenario'], r['steps'], r['pitfall'], r['source']))

    elif a.cmd in ('script', 'scripts'):
        rows = c.execute(
            "SELECT scene, line, usage, source FROM scripts "
            "WHERE scene||line||usage LIKE ? LIMIT ?", ('%' + a.kw + '%', a.n)).fetchall()
        out(rows, lambda r: "「%s」%s\n   用法：%s  〔%s〕" % (r['scene'], r['line'], r['usage'], r['source']))

    elif a.cmd in ('case', 'cases'):
        rows = c.execute(
            "SELECT title, situation, lesson, source FROM cases "
            "WHERE title||situation||lesson LIKE ? LIMIT ?", ('%' + a.kw + '%', a.n)).fetchall()
        out(rows, lambda r: "· %s\n  处境：%s\n  教训：%s  〔%s〕"
            % (r['title'], r['situation'], r['lesson'], r['source']))

    elif a.cmd in ('principle', 'principles'):
        rows = c.execute(
            "SELECT text, source FROM principles WHERE text||source LIKE ? LIMIT ?",
            ('%' + a.kw + '%', a.n)).fetchall()
        out(rows, lambda r: "· %s  〔%s〕" % (r['text'], r['source']))

    elif a.cmd == 'read':
        r = c.execute("SELECT * FROM docs WHERE id=?", (a.kw,)).fetchone()
        if not r:
            print('无此 id')
        else:
            print('# %s 〔%s〕  %s字\n' % (r['title'], r['tier_cn'], r['clean_chars']))
            print(decode(r['content'])[:8000])

    elif a.cmd == 'stats':
        n, ch = c.execute("SELECT COUNT(*), SUM(clean_chars) FROM docs").fetchone()
        print('原始语料：%d 篇 / %d 字' % (n, ch))
        for t in ('concepts', 'techniques', 'scripts', 'cases', 'principles'):
            print('%-12s %d 条' % (t, c.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]))
        print('\n分类分布：')
        for r in c.execute("SELECT tier_cn, COUNT(*) c FROM docs GROUP BY tier_cn ORDER BY c DESC"):
            print('  %-8s %d' % (r['tier_cn'], r['c']))
        print('\n数据库：%.1f MB' % (os.path.getsize(DB) / 1048576))
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
