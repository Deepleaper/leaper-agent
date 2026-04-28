# Changelog

## v0.8.0 (2026-04-28)

### 🧠 DeepBrain 六层自进化记忆引擎
- L0: BM25 + Vector RRF 混合召回，Ollama nomic-embed-text 768 维向量
- L1: 四维经验提取 + 4Gate 质量门控，cosine > 0.85 自动去重
- L2: 经验聚类 → 技能生成，本地 LLM 优先
- L3: 技能合并/淘汰/晋升 + 漂移检测
- L4: 多维用户画像，自动从对话中构建用户心智模型
- L5: 一致性校验 + 回归防护 + 衰减机制
- backfill_embeddings()：首次启动自动补齐旧数据向量

### ⚡ LLM 分层降级
- L0/L5: 纯规则/纯向量，零 token
- L1/L2: 本地 Ollama 优先 → 质量门控 → 云端 fallback
- L3: 本地 Ollama（简单逻辑，够用）
- L4: 直接云端（用户画像需要深度理解）
- 月均 API 成本降低 80-90%，随对话量增长保持稳定

### 🔍 DuckDuckGo 搜索
- 零配置搜索，无需 API Key，开箱即用
- 自动 fallback 链：Firecrawl → Tavily → DuckDuckGo
- 配置了更好的搜索工具就自动升级，未配置也不影响使用

### 🎯 Telegram 优化
- 菜单从 100 个开发者命令精简到 2 个（/new, /help）
- 面向普通用户，减少认知负担

### 🐛 修复
- brain.db 路径解析修复（跨目录启动不再出错）
- Evolution LLM model 名称 fallback（Ollama 模型名不一致时自动兜底）
- `_merge_skills` break 位置修复（技能合并逻辑错误）
- per-session mutex 修复（并发请求不再互相阻塞）

---

## v0.7.1 (2026-04-27)

### 产品体验
- 🔇 工具调用过程不再暴露给用户（terminal、read_file、search_files 等）
- 🔇 中断/排队提示静默（不再发 "⚡ Interrupting current task"）
- 🔇 后台记忆整理消息静默（不再发 "⚠ Auxiliary background review failed"）
- 🔇 首次连接不再弹 "📬 No home channel" 提示
- 🔒 工具执行确认默认关闭（approvals.mode: off）
- 🏷️ 用户可见文本去除第三方品牌引用

### 修复
- 🐛 `write_hermes_config()` 生成正确的 named provider 格式（修复自定义 API 401 问题）
- 🐛 `TELEGRAM_HOME_CHANNEL` 自动从 allowed users 推导
- 🐛 system prompt 加入工具调用静默规则，防止 LLM 暴露工具使用细节

### 文档
- 📝 README.md 全面重写（面向普通用户，中文原生）
- 📝 新增 QUICKSTART.md（5 分钟快速开始指南）

### 模板
- 📝 CEO Coach EGO.md 加强工具调用不可见规则

## v0.7.0 (2026-04-27)

### 首个 Python 版本
- 基于 Hermes Agent (MIT) Fork
- 新增 Leaper Brain（SQLite 持久记忆）
- 新增六层进化引擎（L0-L5）
- 新增 leaper.yaml 简化配置
- 新增 CLI（leaper init/run/chat/workshop/status）
- 新增 CEO Coach 模板
- 新增 Workshop 模板系统
