"""kingdee_console —— MCP/Ontology 之上的管理控制台。

把「现有的 MCP 接口」（kingdee_mcp 的 97 个 legacy 工具 + kingdee_ontology
base 层的 11 个 kd_* 通用动词工具）统一包一层，给人用的 Web 控制台
（Dashboard + 对话窗口）用，同时为后续企业级多助理 A2A 打地基。

分层（谁能看到什么）：

    浏览器 / 对话界面 / 其它 agent 的 A2A 请求
            │  只走 HTTP，只看到工具名 + JSON schema + 结构化结果
            ▼
    kingdee_console（本包，唯一持有凭据/账套信息的边界层）
            │  在同一个进程里直接调用 FastMCP 的 list_tools/call_tool，
            │  复用 kingdee_mcp.server 已有的 _session_id 登录缓存——
            │  不是每次请求都重新登录，也不单独起子进程管生命周期。
            ▼
    kingdee_ontology.base / kingdee_mcp.server（真正连金蝶的那一层）
"""
