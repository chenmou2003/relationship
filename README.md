# 情感导师 · Relationship Mentor Skill

一个 **WorkBuddy 技能 + 离线知识库**，面向两性 / 亲密关系、情感沟通、吸引力建设与长期关系经营的教练场景。

知识底座是 **1637 篇中文情感课程转写稿（约 986 万字）**，炼化成可检索的 SQLite 数据库 + 一组 Markdown 参考文档。**每次回答前必须先检索，凭语料说话。**

> English: A WorkBuddy skill + offline SQLite knowledge base for dating / intimate-relationship coaching, distilled from 1,637 Chinese course transcripts (~9.86M chars). Every answer must be grounded in a corpus query first. Code is MIT; the underlying course text is third-party — see [版权与免责声明](#版权与免责声明).

---

## 一眼看懂

| 项 | 值 |
|---|---|
| 原始语料 | 1637 篇 / 9,858,313 字 |
| 技法 / 话术 / 案例 | 277 / 273 / 158 条 |
| 概念 / 原则 | 292 / 329 条 |
| 数据库体积 | **12.9 MB**（`database/mentor.db`，可直接网页上传 GitHub） |
| 全库检索耗时 | 约 0.2 秒（Python 端扫描，无需 FTS 索引） |
| 依赖 | 仅 Python 3.8+ 标准库，零第三方包 |

**越用越准**：`scripts/object_learn.py` 会归档你提供的对话记录，累积成对象画像和「哪些做法对这个对象有效」的打法库，逐步输出定制化方案。档案存在系统应用数据目录，不进仓库。

**为什么这么小**：原文用 zlib 压缩存储（27.5MB → 11.1MB），并且**不建 FTS5 倒排索引**（trigram 索引单独就要 63.5MB）。实测全库子串扫描只要 0.01 秒，索引纯属浪费——去掉它，数据库从 98.9MB 降到 12.9MB，正好卡在 GitHub 网页上传 25MB 单文件上限之内。

---

## 目录结构

```
relationship-mentor/
├── SKILL.md                      # Agent Skills 封装（WorkBuddy/Claude Code/Codex/Gemini/OpenCode）
├── AGENT.md                      # 通用技能规范（与平台无关）★ 主规范、唯一真源
├── AGENTS.md                     # 项目内 agent 通用入口（Claude Code/Codex/Cursor/Windsurf…）
├── CLAUDE.md                     # → 转发到 AGENTS.md
├── system_prompt.md              # 可直接粘贴的系统提示
├── mcp.example.json              # MCP 配置示例
├── README.md                     # 本文件
├── LICENSE                       # MIT（仅限代码与结构）
├── .gitattributes / .gitignore
├── database/
│   └── mentor.db                 # 12.9 MB，原文 zlib 压缩，无 FTS 索引
├── references/
│   ├── corpus/                   # 语料提炼（与 mentor.db 同源）
│   │   ├── 00_总纲与诊断框架.md    # 五阶段流程 + 诊断树 + 用户画像（每次先读）
│   │   ├── 03_技法清单.md          # 277 条技法（场景/步骤/坑/来源）
│   │   ├── 04_话术库.md            # 273 条话术
│   │   ├── 05_案例库.md            # 158 个真实咨询案例
│   │   ├── 06_概念与原则.md        # 292 概念 + 329 原则
│   │   ├── 07_语料地图.md          # 20 个主题 → 代表性原文 id
│   │   └── 分批提炼/               # 20 份完整提炼稿
│   ├── knowledge/                # 20 份补充知识（依恋 / MBTI / 冲突修复 / 同意边界 /
│   │                             #   PUA 伦理替代 / 在线约会 / 中国法律与危机转介 …）
│   └── practical/                # 23 份沟通实战（话术编排 / 场景松弛感 / 投入失衡与退出 /
│                                 #   主动表达 / 长期档案 / 导读与使用分级 …）
├── scripts/
│   ├── query.py                  # 检索 CLI（透明解压 + 全库扫描）
│   ├── object_learn.py           # 对象学习：归档对话 → 画像 → 打法库（越用越准）
│   ├── memory_store.py           # 长期关系档案（同意制、可撤销、有上限）
│   ├── mcp_server.py             # MCP 服务器（stdio，零依赖）★ 任意 MCP 客户端可用
│   ├── install.py                # 一键安装到本机各 agent 技能目录 / 输出 MCP 配置
│   ├── validate_skill.py         # 结构校验 + 上传体积检查
│   └── pipeline/                 # 构建 / 增量入库 / 导出脚本（维护者用）
│       ├── _compress_db.py       # 重建小体积数据库（压缩 + 去 FTS）
│       ├── _build_db.py / _load_digest.py / _load_incremental.py / _export_refs.py
│       └── distill/              # 结构化提炼产物 struct_*.json
└── .backup/                      # 合并前的原始副本（本地保留，已 gitignore）
```

---

## 核心规则：先查库，再说话

不是开场查一次就完事。**每一次要给出判断、方法、话术或结论之前，都得先有检索结果摆在面前**；思考过程要能指出依据出自哪条技法 / 话术 / 案例或原文 #id。没查过就说，等于编。

```bash
python scripts/query.py stats                  # 库统计
python scripts/query.py search "已读不回" -n 5  # 全文检索（多词用空格分隔，按命中次数排序）
python scripts/query.py tech 邀约 -n 5          # 技法（场景/步骤/坑/来源）
python scripts/query.py script 破冰 -n 5        # 话术
python scripts/query.py case 冷淡 -n 5          # 案例
python scripts/query.py concept 需求感 -n 5      # 概念
python scripts/query.py principle 吸引力 -n 5    # 原则
python scripts/query.py read 1417               # 读某篇原文（前 8000 字）
python scripts/validate_skill.py                # 校验技能结构与上传体积
```

`search` 走 Python 端扫描：解压 → 统计各篇关键词命中次数 → 按次数降序（同次数时短文优先）→ 输出标题与上下文片段。默认返回 10 条，用 `-n` 调整。

---

## 接入任意 agent（五种方式任选，可并存）

本技能**不绑定任何平台**：行为规范写在平台无关的 `AGENT.md` 里，其余文件都是不同形态的装载入口。

### 1. 技能目录（推荐）

`SKILL.md` 的 frontmatter 遵循 **Anthropic Agent Skills** 规范，WorkBuddy / Claude Code / Codex / Gemini CLI / OpenCode 等可直接加载。用脚本一键发现本机 agent 并安装：

```bash
python3 scripts/install.py                    # 检测本机有哪些 agent 技能目录
python3 scripts/install.py --install claude   # 装某一个
python3 scripts/install.py --install all      # 全装
python3 scripts/install.py --uninstall claude # 卸载
```

覆盖 `~/.workbuddy/skills`、`~/.claude/skills`、`~/.codex/skills`、`~/.cursor/skills`、`~/.gemini/skills`、`~/.config/opencode/skills`。手工装就是复制整个目录过去：

```bash
cp -r relationship-mentor ~/.workbuddy/skills/relationship-mentor     # macOS / Linux
# Windows: cp -r relationship-mentor "C:\Users\<你>\.workbuddy\skills\relationship-mentor"
```

> 安装前可删掉 `.backup/`（合并前副本，约 101MB，本地回滚用）。

### 2. MCP（免复制，任意支持 MCP 的客户端）

`scripts/mcp_server.py` 是**纯标准库**的 MCP 服务器（stdio / JSON-RPC 2.0 / 协议 2024-11-05），把语料检索和对象学习都暴露成工具：

```bash
python3 scripts/install.py --print-mcp   # 输出填好绝对路径的配置
# 或 Claude Code：
claude mcp add relationship-mentor python3 /绝对路径/relationship-mentor/scripts/mcp_server.py
```

把输出合并进客户端配置即可（Claude Desktop 的 `claude_desktop_config.json`、Cursor 的 `~/.cursor/mcp.json`、Windsurf、Cherry Studio、Dify、Coze…），另见 `mcp.example.json`。

暴露的工具：

| 工具 | 作用 |
|---|---|
| `corpus_search` / `corpus_tech` / `corpus_script` / `corpus_case` / `corpus_concept` / `corpus_principle` | 语料检索（原文 / 技法 / 话术 / 案例 / 概念 / 原则） |
| `corpus_read` / `corpus_stats` | 读原文 / 库统计 |
| `object_brief` / `object_profile` / `object_list` | 对象画像 / 完整档案 / 列表 |
| `object_ingest` / `object_note` / `object_outcome` | 归档对话 / 写观察 / 记录做法效果 |

服务器的 `instructions` 已写入「先检索再回答」的硬性要求，客户端加载时会自动注入。

### 3. AGENTS.md / CLAUDE.md（项目内 agent）

Claude Code、Codex CLI、Cursor、Windsurf、OpenCode、Aider、Cline 会自动读取项目根目录的 `AGENTS.md`（Claude Code 还读 `CLAUDE.md`）。把本仓库挂成项目子目录，或把 `AGENTS.md` 内容并入项目自己的 `AGENTS.md`。

### 4. 系统提示（ChatGPT 自定义 GPT / 网页 agent）

把 `system_prompt.md`（精简）或 `AGENT.md`（完整）粘进系统提示 / 自定义指令。

### 5. 无文件访问的轻量 agent

只能靠上下文：贴 `references/corpus/` 的关键文档。此时检索不到 1637 篇原文，需在回答里说明依据来自提炼文档。

---

## 检索命令详解

> `python` 与 `python3` 等价，仅需 Python 3.8+ 标准库。

| 命令 | 作用 |
|------|------|
| `search <关键词> [-n N]` | 全库扫描，返回标题 + 命中次数 + 上下文片段 |
| `concept <关键词> [-n N]` | 概念表模糊匹配 |
| `tech <关键词> [-n N]` | 技法表匹配，输出「场景/步骤/坑」 |
| `script <关键词> [-n N]` | 话术表匹配（台词为示范，非固定台词） |
| `case <关键词> [-n N]` | 案例表匹配（处境 → 教训） |
| `principle <关键词> [-n N]` | 原则表匹配 |
| `read <id>` | 按 id 读原文前 8000 字 |
| `stats` | 各表条数、分类分布、数据库体积 |

---

## 对象学习档案（越用越准）

技能会随使用积累：把用户给的对话记录归档成**对象画像**，把「哪些做法真的有效」沉淀成打法库，逐渐给出针对这个人的指导。

```bash
# 1) 归档一段对话（自动算行为指标）
python scripts/object_learn.py ingest --subject A --file chat.txt --me 张三 --alias 小雅 --note "认识三周"
# 2) 手写观察
python scripts/object_learn.py note --subject A --field 雷区 --value "反感查户口式提问"
# 3) 记录某个做法的实际效果（定制化的引擎）
python scripts/object_learn.py outcome --subject A --method "用共同兴趣切入" --verdict 有效 --evidence "她主动回问"
# 4) 下次咨询先跑 brief，拿到画像 + 有效/无效 + 建议检索关键词
python scripts/object_learn.py brief --subject A --goal "约出来"
# 其他
python scripts/object_learn.py profile --subject A           # 完整画像与历次归档
python scripts/object_learn.py list                          # 所有对象
python scripts/object_learn.py forget --subject A --confirm  # 删单个对象
python scripts/object_learn.py purge --confirm               # 全清
```

### `ingest` 算什么

从可见原文里统计，并给出**判定依据**（不是拍脑袋打分）：

| 指标 | 含义 |
|---|---|
| 短回复率 | 对方 ≤4 字且无提问的消息占比，高 = 敷衍 |
| 提问率 | 对方主动回问占比，高 = 在延伸话题 |
| 展开率 | 对方 ≥15 字的长回复占比 |
| 回避措辞次数 | 忙 / 再说 / 下次 / 看情况 / 睡了 等 |
| 连续未回应段 | 你连发 2 条以上对方不接的次数 |
| 平均回复间隔 | 有时间戳时计算（分钟） |
| 投入度 | 高 / 中 / 低，附依据句子 |

支持 `名字: 内容` 与 `2026-09-14 21:03 名字: 内容` 两种格式，也读 stdin；说话人多于两个时用 `--me` 指明你自己。

### 边界

- 指标只描述**可见原文里的行为**，不外推成人格、动机，不断言「她喜欢你 / 不喜欢你」；样本不足 3 次只能当参考。
- 归档前报备一句，用户明确说不要才不存。
- 数据库在系统应用数据目录（`~/Library/Application Support/relationship-mentor/objects.sqlite3`，可用 `RELATIONSHIP_MENTOR_MEMORY_DIR` 覆盖），**不在仓库里，不会跟着 push 到 GitHub**。
- 上限：每对象 30 份归档 / 60 条观察 / 40 条打法，超出自动淘汰最旧的。

---

## 长期关系档案（默认关闭）

`scripts/memory_store.py` 可跨会话记住对象与关键事件，**默认不启用**：

```bash
python scripts/memory_store.py status                       # 查看状态
python scripts/memory_store.py enable --confirm              # 用户明确同意后启用
python scripts/memory_store.py apply --json '{"scope":"object","subject_id":"A","field":"MBTI","value":"INFP","source_type":"user_explicit","confidence":"high"}'
python scripts/memory_store.py context --subject-id A        # 召回压缩上下文
python scripts/memory_store.py undo                          # 撤销上一次写入
python scripts/memory_store.py revoke --delete --confirm     # 撤回同意并删除全部
```

边界：只存有限字段与关键事件（总量上限 200 条），不保存整份聊天；用户稳定档案只接受用户明确陈述，模型推断只能写入带置信度的假设；随时可查看、暂停、撤销、删除。数据库在系统应用数据目录（macOS 为 `~/Library/Application Support/relationship-mentor/memory.sqlite3`），可用 `RELATIONSHIP_MENTOR_MEMORY_DIR` 覆盖。

---

## 内容安全红线（一票否决）

1. 对方说「不」即停止；任何推进建议都附「明确拒绝即停、不纠缠、不施压」。
2. 不输出基于性别 / 婚育 / 身份 / 地域 / 外貌的贬低或歧视（可描述群体倾向，须标注「群体≠个体」）。
3. 语料的 PUA 黑话必须转译：框架→边界与一致性；收尾→导向下一步；服从性→双向投入；Alpha/Beta→内在稳定 vs 讨好；预选→真实社交生活。
4. 家暴、跟踪、威胁、自伤、亲密关系暴力、财务控制、金钱诈骗——先确认安全，转介专业 / 法律 / 紧急帮助。
5. 不打包票，不承诺「照做一定追到 / 挽回」。
6. 不诊断心理疾病，不用标签替代行为证据。

---

## 维护者：重建知识库

数据库为预构建产物，普通用户无需重建。重建需要**原始 1637 篇语料**（不在本仓库，因版权不随附）与 `_docs_meta.json`。`scripts/pipeline/` 下的脚本**硬编码了原始语料的工作区绝对路径**，换机器前需先改。

1. `_prep.py` / `_classify.py`：清洗、去广告、按 15 类打标。
2. `_scan.py` / `_titles.py` / `_topics.py` / `_merge_src.py`：标题与主题路由表。
3. `_build_db.py`：构建 `docs` 表（这一步原文是未压缩的）。
4. 蒸馏产物 `distill/struct_NN.json` → `_load_incremental.py 3 12 15 ...` 增量入库（按 name 去重）。
5. `_export_refs.py`：由 DB 重新生成 `references/corpus/03–07`。
6. **`_compress_db.py`：把原文压缩成 BLOB、去掉 FTS 索引、VACUUM，产出可上传的 12.9MB 版本。**

> `_load_digest.py` 会清空全表再重载，仅用于全量重建；补批请用 `_load_incremental.py`。

---

## Git 与上传

- 数据库 12.9MB，低于 GitHub 网页上传的 25MB 单文件上限，**可直接拖拽上传，无需 Git LFS**。`.gitattributes` 已不再把 `mentor.db` 交给 LFS。
- `.backup/` 已加入 `.gitignore`，不会误传。
- 想确认体积是否仍然合规：`python scripts/validate_skill.py`（会检查单文件 25MB 上限与总体积）。

---

## 版权与免责声明

- **代码与技能结构**（SKILL.md、AGENT.md、scripts、README、LICENSE）以 MIT 许可发布。
- **`references/knowledge/` 与 `references/practical/`** 共 43 份文档，改写自开源项目 goutoujunshi（MIT，© powerycy），在此致谢。
- **知识库内容**（`mentor.db` 及 `references/corpus/`）提炼自大量**第三方付费情感课程转写稿**，原始著作权归各自原作者 / 机构。本仓库仅作**个人学习、研究与本地检索**之用，不对原始课程文本做商业再分发。
- **建议以私有仓库托管**，避免课程原文公开扩散引发版权纠纷。
- 本技能输出为通用关系建议，**不构成心理咨询、法律或医疗意见**；涉及安全 / 暴力 / 自伤 / 诈骗等情形，请优先寻求专业与紧急帮助。

---

## License

代码部分：MIT — 见 [LICENSE](./LICENSE)。

## 致谢

知识底座来自 1637 篇中文情感课程语料；健康内核（心态内功、真实咨询案例、痕迹识人等）被优先取用，偏激与操控性内容已按红线剔除与转译。方法论与实战话术部分参考了开源项目 goutoujunshi（MIT）。
