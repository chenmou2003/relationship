# CLAUDE.md

Claude Code 会优先读本文件。本仓库是「情感导师」技能包，行为准则见：

- [`AGENTS.md`](./AGENTS.md) — 通用入口（含检索命令、工作流、对象学习、红线）
- [`AGENT.md`](./AGENT.md) — **完整规范，唯一真源**
- [`system_prompt.md`](./system_prompt.md) — 精简可粘贴版

**最重要的一条**：回答任何情感 / 恋爱 / 沟通问题之前，必须先跑 `scripts/query.py` 检索并引用来源。没检索就回答等于编。
