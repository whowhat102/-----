# 🦏 灵犀客服 · 拟人化智能聊天机器人

一款「先学习、再上岗」的拟人化客服机器人 Web 应用：导入话术模板与业务知识后，
像真人一样接待线上来访者（产品咨询 / 合作洽谈），杜绝机器腔回复，
支持多场景 × 多人群适配与持续纠错训练。

## 快速开始

```bash
# Windows：双击 run.bat（或命令行执行）
run.bat

# Linux / macOS / Git Bash
bash run.sh
```

浏览器打开 <http://127.0.0.1:8000> 即可使用。
首次启动自动建库并灌入「拾光皮具工作室」完整演示数据，开箱即可对话。

> 仓库不含运行数据库与任何 API Key。`data/chatbot.db` 在首次启动时自动生成，
> 并被 `.gitignore` 排除；请勿手动提交或分享该文件。

## 六大功能

| 模块 | 说明 |
|---|---|
| 💬 对话测试 | 以"来访者"身份发消息测试机器人；实时显示引擎模式、命中的知识、转人工标记；👍/👎 评分 |
| 📚 知识库 | 产品知识条目 CRUD + 批量导入（`标题 \| 内容 \| 标签`），机器人只依据知识回答，不编造 |
| 🎭 人设管理 | 姓名/身份/开场问候/口头禅 + 口语化·热情度·正式度三滑杆 + 表情风格，可建多套人设 |
| 📝 话术模板 | 按 开场/引导/报价/促成/收尾 五阶段管理话术，支持 `{产品名}` `{价格}` 变量 |
| 🎯 场景与人群 | 售前/合作/议价/售后四场景策略 × 个人/企业/批发/学生四人群语气，可自定义 |
| 🛠️ 训练中心 | 聊天中 👎 并写下理想回复即沉淀为纠错样本；相似问题再现时作为标准答案注入 |

## 回复引擎（双模式）

- **🧪 模拟引擎**（默认）：无需任何 Key，规则匹配知识库 + 话术套用 + 人设风格化改写，跑通全部流程演示。
- **🤖 真实大模型**：设置页填入任意 OpenAI 兼容接口即可切换——
  - DeepSeek（推荐）：`https://api.deepseek.com`，模型 `deepseek-flash`（或 `deepseek-v4-pro`）
  - 智谱：`https://open.bigmodel.cn/api/paas/v4`，模型如 `glm-4-flash`
  - OpenAI：`https://api.openai.com/v1`，模型如 `gpt-4o-mini`
  - 本地 Ollama：`http://127.0.0.1:11434/v1`

  > ⚠️ DeepSeek 旧模型名 `deepseek-chat` / `deepseek-reasoner` 已于 **2026-07-24** 停用，
  > 请改用 `deepseek-flash`（当前为 DeepSeek-V4.1-Flash-1017）。

  系统提示词由「人设风格 + 场景策略 + 人群语气 + 检索知识 + 阶段话术 + 纠错示例 + 反机器腔回复铁律」
  动态组装，这是回复拟人度的核心。大模型调用失败时自动降级模拟引擎，对话不中断。

### 接入 DeepSeek（最小步骤）

1. 注册/登录 [DeepSeek 开放平台](https://platform.deepseek.com/api_keys)，在「API keys」页创建 Key 并**立即复制保存**（通常只完整显示一次）；账户需有可用余额（充值或赠送余额均可）。
2. 二选一提供 Key：
   - **界面方式**：设置页 → 选「真实大模型」→ 点「一键填入 DeepSeek 官方配置」→ 粘贴 Key → 保存。
   - **本地 `.env` 文件**（推荐，最省心）：把 `.env.example` 复制为 `.env`，填入真实 Key，
     启动时自动读取，无需每次敲命令；`.env` 已被 `.gitignore` 排除，不会上传。
   - **直接设环境变量**（优先级高于 `.env` 和数据库）：
     ```bash
     # Windows PowerShell（仅当前会话）
     $env:DEEPSEEK_API_KEY="sk-你的真实Key"
     # Git Bash / macOS / Linux
     export DEEPSEEK_API_KEY="sk-你的真实Key"
     ```
     可选变量：`DEEPSEEK_API_BASE_URL`、`DEEPSEEK_MODEL`、`DEEPSEEK_THINKING=enabled`
     （默认关闭思考模式，使「温度」滑杆生效并降低延迟/费用）。
   - **界面方式**：设置页 → 选「真实大模型」→ 点「一键填入 DeepSeek 官方配置」→ 粘贴 Key → 保存
     （该方式会把 Key 写入本机数据库，请勿上传 `data/chatbot.db`）。
3. 点「测试大模型连接」，返回「连接成功，模型回复：…」即接入完成；随后正常对话即可。

## 安全边界与合规

- 超纲问题 / 售后纠纷 / 大额合作 / 情绪激动 → 机器人礼貌收集联系方式并打上 **⚠ 转人工** 标记。
- 设置页提供「声明机器人身份」开关：部分地区/平台法规要求机器人披露身份，请按你的使用场景决定是否开启。

## 技术架构

```
web/            前端单页应用（原生 HTML/CSS/JS，无外部 CDN 依赖）
server/
  main.py       FastAPI 入口 + 静态托管
  db.py         SQLite 建表 + 种子数据（data/chatbot.db）
  schemas.py    Pydantic 模型
  engine/
    prompt.py   系统提示词组装（核心）
    mock.py     规则模拟引擎
    llm.py      OpenAI 兼容大模型客户端
    retrieve.py 中文字符二元组轻量检索
  routers/      knowledge / config / chat / settings 四组 REST API
```

依赖仅 `fastapi` `uvicorn` `httpx` 三个包。

## API 一览

`GET /api/health` · 人设/知识/话术/场景/人群 CRUD ·
`POST /api/sessions` · `POST /api/chat` · `POST /api/feedback` ·
`GET /api/corrections` · `GET|PUT /api/settings` · `POST /api/settings/test`

## 注意事项

- API Key 默认只保存在本机 SQLite（`data/chatbot.db`）；若用 `DEEPSEEK_API_KEY` 环境变量提供，
  则完全不落库。服务端不会把 Key 转发给除所填 Base URL 之外的第三方；请勿把数据库文件分享给他人。
- 本应用为单机单用户设计，未做登录鉴权，请勿直接暴露到公网。
- 对接微信等真实 IM 平台涉及平台协议限制，建议通过官方合规通道（企业微信客服 API 等）二次开发。

## 后续迭代方向

流式输出（SSE）· 向量检索/embedding · 多知识库分组 · 对话数据导出 · 话术 A/B 测试 · 真实 IM 平台对接
