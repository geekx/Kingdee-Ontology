# Kingdee Console（前端）

Dashboard + 对话窗口的前端，React + Vite + TypeScript + Tailwind。
后端是仓库里的 `kingdee_console`（FastAPI），默认跑在 `http://127.0.0.1:8787`。

## 跑起来

```bash
# 后端（仓库根目录）
pip install -e ".[console]"
kingdee-console                 # 默认演示模式，不连真账套

# 前端（本目录）
npm install
npm run dev                     # http://localhost:5173，/api 已代理到 8787
```

对话窗口要调用 Claude 做意图识别，需要设 `ANTHROPIC_API_KEY`（启动后端前
`export` 即可）；没配时对话会优雅降级成一条"意图识别暂时不可用"的提示，
Dashboard 的能力目录、租户/角色/助理管理、A2A demo 不受影响。

## 目录

- `src/pages/Dashboard.tsx` —— 能力矩阵（按单据/基础资料/视图/系统四类上色）、
  多租户/角色/助理管理、A2A 跨助理请求 demo 面板。
- `src/pages/Chat.tsx` —— 对话窗口：助理选择、对话历史侧栏、消息流，
  助理回复按实际调用的能力（动词+名词）上色。
- `src/api.ts` —— 后端 REST API 的薄封装。
