# Kingdee MCP 上架清单（Publish Guide）

本文件汇总把 **kingdee-mcp**（MCP 服务器）及其配套 **kingdee-query**（WorkBuddy 技能）发布到市场所需的一切。
所有外部发布动作（上传 PyPI / 推 GitHub / 提交 ClawHub）都需你手动执行或在确认后进行，**本指南只产出材料与步骤**。

---

## 0. 现状盘点

| 项 | 值 |
|----|----|
| PyPI 包名 | `kingdee-mcp`（`kingdee_ontology` 与 `kingdee_mcp` 同一个发行版，不是两个包） |
| 已发布版本 | **0.2.1**（PyPI 现状），本地 `pyproject.toml` 已是 **0.3.0**——已 `python -m build` + `twine check` + 装进干净 venv 实测导入/入口点都正常，**尚未打 tag、未上传** |
| GitHub | https://github.com/geekx/KingdeeMCP |
| 官网 | https://wahailong.github.io/KingdeeMCP/ |
| 工具数 | legacy 86 个（`kingdee-mcp`）+ 底座 11 个（`kingdee-ontology`） |
| 启动入口 | `uvx kingdee-mcp`（legacy 86 工具）／`uvx --from kingdee-mcp kingdee-ontology`（底座 11 工具，同一个发行版里的另一个脚本）／`python -m kingdee_mcp.server` |
| 认证方式 | 金蝶 WebAPI **账号密码(ValidateUser)**，无需 AppID / AppSecret |
| 配置文件 | `pyproject.toml`（hatchling，脚本 `kingdee-mcp` / `kingdee-ontology` / `kd-logic` / `kingdee-setup-check`） |

### 发布 0.3.0 到 PyPI 的方式（人工触发，不要自动化）

`.github/workflows/publish.yml` 已配好 Trusted Publishing（OIDC，无需 token），触发条件是
`push tag v*` 或手动 `workflow_dispatch`。**故意不设成每次 push 自动发布**——发布是不可逆
操作（PyPI 不允许覆盖同版本号），且会消耗 GitHub Actions 分钟数，必须由人决定"现在发"：

```bash
# 方式一：打版本 tag（会真的触发发布，确认要发再执行）
git tag v0.3.0
git push origin v0.3.0

# 方式二：GitHub 网页 Actions 标签页 → Publish to PyPI → Run workflow（无需先打 tag）
```

两种方式都会用当前 `main` 分支的 `pyproject.toml` 版本号打包上传，发布前确认版本号、
CHANGELOG 都已经是想发布的状态。

---

## 1. 发布前自检（Checklist）

- [ ] **版本号**：若要以 0.2.0 上架，先 `python -m build` 后 `twine upload dist/*`（本机 `~/.pypirc` 已配 token）。
- [ ] **README 完整**：安装 / 配置 / 环境变量 / 工具表 / 示例 / FAQ 已齐（当前 README 已较完整）。
- [ ] **LICENSE**：MIT（已有 `LICENSE`）。
- [ ] **CHANGELOG**：已有 `CHANGELOG.md`，记录 0.2.0 的破坏性变更（移除 AppID/AppSecret，改密码登录）。
- [ ] **无硬编码密钥**：所有凭证走环境变量，未写入源码（已合规）。
- [ ] **示例充分**：`examples/` 已含 9+ 业务场景。
- [ ] **配套技能**：`skill/kingdee-query/`（SKILL.md + README）已就绪，作为"语义路由"技能随仓库发布。
- [ ] **接入模板**：`examples/workbuddy-mcp-config.example.json` 已提供，含占位符。

---

## 2. 发布 MCP 服务器到 ClawHub

> ClawHub（https://clawhub.ai/）是 OpenClaw / WorkBuddy 生态的官方技能与 MCP 市场，支持 GitHub 登录与仓库地址导入。

1. 访问 https://clawhub.ai/ ，用 **GitHub 账号** 登录。
2. 点击 **"发布技能 / 发布 MCP"**（提交类型选 **MCP Server**）。
3. **上传方式**：填写 GitHub 仓库地址 `https://github.com/WaHaiLong/KingdeeMCP`，或上传本地文件夹。
4. 填写信息：
   - 名称：`kingdee-mcp`
   - 描述：金蝶云星空（Kingdee Cloud）MCP 服务器，让 AI 用自然语言查询与操作 ERP（销售/采购/库存/生产/成本/资产等 86 个工具）。
   - 版本：`0.2.0`（与 PyPI 对齐）
   - 标签：`erp` `金蝶` `kingdee` `mcp` `k3cloud`
   - 启动命令：`uvx kingdee-mcp`
   - 所需环境变量（**只写变量名，不写真实值**）：`KINGDEE_SERVER_URL` / `KINGDEE_ACCT_ID` / `KINGDEE_USERNAME` / `KINGDEE_PASSWORD` / `KINGDEE_LCID`
5. 提交审核，通常 **1–3 个工作日** 完成安全扫描与功能测试。
6. 审核通过后上架，其他用户可一键安装或复制 mcp.json 片段接入。

---

## 3. 发布配套 Skill（kingdee-query）到市场

仓库内 `skill/kingdee-query/` 即技能包，三种上架路径：

- **ClawHub**：登录 → 发布技能 → 上传 `skill/` 目录或填仓库地址 → 填名称/描述/版本/标签 → 提交审核。
- **WorkBuddy 官方推荐市场（BuiltinMarket）**：在 WorkBuddy 内用 `workbuddy skills publish ./skill/kingdee-query`（命令来自腾讯云 Techpedia / 社区教程，建议以应用内"技能管理 / 发布"入口或官方开发者平台最新说明为准），过安全扫描 + 审核后上架，其他用户可一键安装。
- **GitHub 导入**：WorkBuddy 技能管理选 **"通过 URL 导入"**，填 `https://github.com/WaHaiLong/KingdeeMCP`，并指定 `skill/kingdee-query` 子目录自动拉取。

> 技能与 MCP 是**两个独立上架物**：技能负责"语义路由 + 使用约定"，MCP 负责真正的金蝶连接。两者配合使用体验最佳。

---

## 3b. 发布配套 Skill（kingdee-ontology）到市场

`skill/kingdee-ontology/` 是对象为中心的底座技能（对应 11 工具的 `kingdee-ontology` 入口，
不是 `kingdee-query` 依赖的那个 86 工具 legacy 服务）。提交材料：

| 字段 | 值 |
|------|-----|
| 名称 | `kingdee-ontology` |
| 描述 | 以对象为中心操作金蝶云星空：打开一个对象就能看到属性、当前状态、此刻能做哪些动作（不能做的会说明原因）、连到哪些别的对象；支持查询、提交/审核/下推、租户自定义业务操作编排、卡单排查。 |
| 版本 | 与 PyPI 对齐——**待 0.3.0 正式发布后再填 0.3.0**，发布前先填当前 PyPI 上的 0.2.1 或标注"预发布" |
| 标签 | `erp` `金蝶` `kingdee` `mcp` `k3cloud` `ontology` |
| 上传方式 | 填仓库地址 `https://github.com/geekx/KingdeeMCP`，或上传 `skill/kingdee-ontology/` 目录 |
| 启动命令 | `uvx --from kingdee-mcp kingdee-ontology`（同一发行版里选另一个脚本，**不是** `uvx kingdee-ontology`——PyPI 上没有叫这个名字的独立包） |
| 所需环境变量（只写变量名） | `KINGDEE_SERVER_URL` / `KINGDEE_ACCT_ID` / `KINGDEE_USERNAME` / `KINGDEE_PASSWORD` / `KINGDEE_LCID` |
| 接入模板 | `examples/workbuddy-mcp-config-ontology.example.json`（已提供，含占位符） |

流程同第 2 节：clawhub.ai → GitHub 登录 → 发布技能 → 按上表填写 → 提交审核。

---

## 4. WorkBuddy 用户接入配置（mcp.json）

用户级（所有项目复用）：编辑 `~/.workbuddy/mcp.json`，加入下方 `kingdee` 片段（占位符替换为真实值后重启 WorkBuddy）：

```json
{
  "mcpServers": {
    "kingdee": {
      "command": "uvx",
      "args": ["kingdee-mcp"],
      "env": {
        "KINGDEE_SERVER_URL": "http://YOUR-SERVER/k3cloud/",
        "KINGDEE_ACCT_ID": "YOUR-ACCT-ID",
        "KINGDEE_USERNAME": "YOUR-KINGDEE-USERNAME",
        "KINGDEE_PASSWORD": "YOUR-KINGDEE-PASSWORD",
        "KINGDEE_LCID": "2052"
      }
    }
  }
}
```

- **生产更稳**：用 `pip install kingdee-mcp` 后改为 `"command": "python", "args": ["-m", "kingdee_mcp.server"]`（`uvx` 偶发临时环境缺依赖）。
- **项目级**：仅当前项目生效时，在项目根放 `workbuddy.mcp.json`（结构同上）。
- **可视化**：也可走 插件 → MCP 服务器 → 配置 MCP 的图形界面粘贴，无需手改文件。
- 模板文件见 `examples/workbuddy-mcp-config.example.json`。

---

## 5. 注意事项

- **凭证安全**：`mcp.json` 与任何市场描述中都**只写环境变量名、不写真实密码**；不要把含真实凭证的 `mcp.json` 提交到仓库。
- **LCID**：默认 `2052`（简体中文），按需修改。
- **0.2.0 破坏性变更**：登录从"第三方应用授权(AppID+AppSecret)"改为"账号密码(ValidateUser)"，旧的 `KINGDEE_APP_ID` / `KINGDEE_APP_SEC` 已失效，升级用户须迁移（README 已说明）。
- **权限**：金蝶账号需有对应模块操作权限，否则查询/写操作会报权限拒绝。
- **SQL Server 探查**：4 个 `kingdee_discover_*` 工具需额外配置 `MCP_SQLSERVER_*`（建议只读账号）。

---

## 6. 后续可选项

- 在官网 `wahailong.github.io/KingdeeMCP/` 增加"WorkBuddy 一键接入"说明与 mcp.json 片段。
- 在 ClawHub / 腾讯云 MCP 市场 同步登记，扩大曝光。
- 持续维护：每次改动 bump 版本、更新 CHANGELOG 与 README 工具表。
