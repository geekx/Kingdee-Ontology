# 更新日志 (Changelog)

本项目所有重要变更都会记录在此文件。

格式参考 [Keep a Changelog](https://keepachangelog.com/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

> 当前 PyPI 版本：`0.2.4`（见 `pyproject.toml` 历史；本仓库尚未发布过，下一次打 tag 将发
> `0.4.0`）。本文件按功能里程碑汇总，上游 `WaHaiLong/KingdeeMCP` 与本仓库 `geekx/Kingdee-
> Ontology` 分叉自同一个 `src/kingdee_mcp/server.py`，`0.2.4` 及以下条目两边共享；`0.3.0`
> 起是本仓库独立的本体底座 + 判断层增补，`0.4.0` 把上游 `0.2.2`～`0.2.4` 期间的字段可见化/
> 批量对账/附件/新查询工具等并了回来，详见下方「同步自上游」一节。

---

## [Unreleased]

### 新增：识别报表类二开对象，探测器不再把"问错端点"误当成"没权限"

一次真实排障发现：标准单据探测都正常，但**报表类二开对象**（金蝶后台
"报表"菜单下的自定义报表）一律探测失败——原因不是权限，是探测器问错了
端点。`query()`（`ExecuteBillQuery`）只认单据，报表走的是完全独立的
`GetSysReportData`；不管账号有没有权限，`ExecuteBillQuery` 对报表都会报
"看起来像没权限/表单不存在"的业务错误。这是结构性盲区，不是权限关键词
列表没覆盖全——`ExecuteBillQuery` 从设计上就查不到报表，词表扩多长都补
不上。详见 `docs/ontology/06-report-probing.md`。

`GetSysReportData` 需要真实的 `FieldKeys`/`Model`，因表而异、猜不出来
（有真实案例试了十几种参数组合全部失败），所以探测器**不猜参数**，只做
一件更保守的事：`_probe_unregistered()` 里 `query()` 判定为业务错误后，
追加用空参数试一次 `report()`。金蝶在这种情况下典型会报一个 .NET 风格的
参数缺失异常（形如"值不能为 null。参数名: key"）——这个异常形状本身就是
信号：请求已经进了 `GetSysReportData` 的处理逻辑，说明这大概率是张真实
存在的报表。新增 `possible_report` 分类，专门标记这种情况：**不算"确认
可用"**（没有真实 `FieldKeys` 验证不了完整权限），但至少把"这是报表、
别再当单据猜参数"说清楚，不用让下一个 agent 重复同样的瞎试。

`probe_connection()` 返回体新增 `possible_reports` 计数与对应说明；
`kd_check_profile`/`setup_check` 的报告新增"≈ 疑似报表"标记与提示，指向
`docs/ontology/06-report-probing.md` 的手动接入步骤（F12 抓包拿真实
`FieldKeys`/`Model`）。11 条新测试覆盖：参数缺失异常的关键词识别（两个
标记词都要出现，避免"key"单独出现时误判）、`possible_report` 分类与
WikiSkill 建议、`query()` 成功时跳过报表探测、`report()` 自身异常不影响
原分类、聚合计数与提示文案。

### 新增：探测到本体不认识的表单时，提一条建议而不是丢掉

`probe_connection()` 原本只能测本体里已经注册过的名词——传一个本体不认识
的字符串，此前是静默跳过，用户拿不到任何反馈。现在只要调用方用 `nouns=`
**明确点名**了一个本体解析不出来的候选，就会绕开本体、直接拿这个字符串
当 `form_id` 发一次原始只读查询，看金蝶认不认：

- 金蝶报"表单不存在"这类业务错误 → 按原样归到 `business_error`/
  `no_permission`，只是多标一个 `unregistered: true`；
- 金蝶真的认、查得通 → 说明这是个账号能用、但本体没登记的表单，
  自动提一条建议到 WikiSkill（`unregistered_form_reachable`），供人日后
  决定要不要补进 `profiles/<租户>/profile.yml` 的 `nouns` 段——**只提议，
  不自动改配置**，和 `navigate()` 探测出下推关联字段时的做法一模一样。

`default_candidates()` 挑出来的候选保证已在本体里，不会触发这条兜底路径
——只有调用方自己点名才会，默认自检不会因此多发请求。`kd_check_profile`
与 `setup_check` 的报告都加了这条提示。8 条新测试覆盖分类边界（拒绝不提议、
能查才提议）、权限判断复用同一套关键词启发式、知识库写不进去不连累探测本身。

### 新增：跨 harness 的引导式配置 —— 本地凭据文件 + 连通/权限自检

驱动这套 MCP 的不一定是 Claude Code——Workbuddy、基于 DeepSeek 的 agent 之类
的 harness，注入环境变量的方式并不统一。而装好之后第一次真正知道账号密码
对不对、这个账号能碰到哪些模块，此前往往要等第一次业务查询失败才发现。

**`.env` 本地凭据文件**（`src/kingdee_ontology/envfile.py`）：查找顺序
`$KINGDEE_ENV_FILE` → 当前目录 `.env` → 主目录 `~/.kingdee-mcp.env`。只补
`os.environ` 里没有的键，不覆盖已经通过 MCP 客户端自己方式配置好的变量——
文件是兜底，不是真理来源。两个服务端入口（`kingdee_mcp/server.py`、
`kingdee_ontology/base/server.py`）都在读任何 `KINGDEE_*` 之前接了这一行。
新增 `.env.example` 模板。

**连通与权限探测**（`src/kingdee_ontology/base/probe.py`）：真登录一次，
逐个只读探测几类常见单据，报告哪些能查、哪些像是没权限。三个刻意的设计：

- **只读**，全程只调 `query()`，不碰 `kd_act`；
- **一出问题就停**——Kingdee 明确拒绝（权限不足/表单不存在）不算"出问题"，
  那是探测本来就想知道的答案，继续测下一个；探测本身跑不通（登录失败/
  网络故障）才算，此时立刻停，不把剩下的候选都超时一遍；
- **权限判定是启发式的**，按错误信息里的中文关键词猜，没有拿真实账套
  逐一验证过全部措辞，不确定时归到更保守的 `business_error`。

默认探测候选优先复用 `kingdee_mcp` 那 97 个专用工具背后人工维护的
`FORM_CATALOG`——这些表单久经使用、行为摸得清楚，比单纯按下推出边数量
排序更不容易在探测阶段就先撞上冷门/边缘表单触发的怪问题；不够再按本租户
已配置的业务操作入口、类别、出边数量补齐。

**两个入口**：MCP 会话里 `kd_check_profile(probe=True)`；不需要先接上 MCP
协议、任何能起子进程的 harness 都能跑的 `python3 -m kingdee_ontology.setup_check`
（新增 `kingdee-setup-check` 命令）——退出码 0 正常 / 1 配置或 profile 有问题 /
2 连不上或登录失败，可直接接在安装脚本里当门禁。

顺手修了一处真缺陷：`validate_profile.validate("")`（没配置租户覆盖层，
多数用户的默认状态）此前会报「租户 '' 没有配置文件」——这句话本身就说不通，
压根没有叫"''"的租户，也没人要求它有配置文件。`load_profile("")` 按约定
返回 `None` 表达"没有覆盖层"，`validate()` 原来把这和"指定了一个不存在的
租户"混为一谈。现在没指定租户返回 `([], [])`，指定了不存在的租户名仍照旧
报错。

### 修复：AIP-04/05 的忠告生成了，但没人知道要看它

`Dispatcher.act()` 早就把判断层的忠告塞进 `out["advisories"]`，PR 里也写了
"经 `Dispatcher.act` 的 `advisories` 交出"——这句话在代码层面是真的，但
**从没有任何文档告诉 Claude 要去读它**：`kd_act` 的工具说明没提，`SKILL.md`
没提，也没有一条测试验证这个字段真的会出现在返回体里。于是这个功能对使用它
的 agent 是不可见的——写出来了，但没人会用。

同一个病，第三次犯：装完丢失的失败日志、说反话的审计器，现在是没人知道该看
的忠告字段。都是"代码本身没问题，但外部没人能发现它在工作"。

新增 `tests/test_base_ontology.py::TestActAdvisories` 5 条集成测试，端到端
验证 `advisories` 字段：destructive 动词（如 delete）必带 AIP-04，走「操作」
接口且未给 `operation` 的动词（如 close）必带 AIP-05，给了就不再提醒，
无忠告时字段整个不存在（不必分辨"空数组"和"没有意见"）。

`kd_act` 的工具说明与 `SKILL.md` 都补上了：有 `advisories` 时先念给用户听、
再执行，不要静默略过。

### 同步自上游 `WaHaiLong/KingdeeMCP`（0.2.2 ～ 0.2.4）

本仓库与上游分叉自同一份 `src/kingdee_mcp/server.py`（分叉点 `2c44e6f`）；分叉之后上游
独立演进到 `0.2.4`，本仓库独立演进出本体底座（`0.3.0`）。这次把上游分叉之后的改动合了
回来，详见下方对应版本号的 `## [0.2.4]`/`## [0.2.3]`/`## [0.2.2]` 原文条目，这里只记与
本仓库自有改动的交汇点：

- **会话过期检测**（issue #7，对应上游 `_is_session_expired`）：本仓库独立修过同一类问题
  （`_session_expired`，返回 `(expired, safe_to_replay)` 元组，用于区分"能不能安全重放写
  请求"），但没覆盖 `ctx == null` / `-10001` 这两个金蝶官方标志。合并时把这两个标志并进
  本仓库自己的检测函数，两条修复的覆盖面相加，不是二选一。
- **批量操作对账**（issue #8）：`_result_status()` 新增 `requested_ids` 参数与
  `_reconcile_batch()`，与本仓库已有的 `link_check`（下推链接校验，审计 L-1）参数并存，
  两者互不影响。
- **字段名可见化 + 错误中文化**（issue #9）：`validate_and_fix()` 的 3 元组返回值
  （含 `unknown_fields`）已经在合并时自动生效；本仓库把它接进了自己重构出的共用函数
  `_prepare_save_model()`（审计 A-6，`kingdee_save_bill` 与 `kingdee_create_and_audit`
  共用同一套预处理），所以两个入口现在都带 `unknown_fields`/`auto_fixes`，比上游原版
  （只有 `kingdee_save_bill` 一个入口）覆盖更全。
- **新查询工具**：`kingdee_query_receipts`（收款单 AR_Receivable）、
  `kingdee_query_outsource_orders`（委外加工订单 SUB_SubReqOrder）。
- **单据附件上传/下载**：`kingdee_upload_attachment` / `kingdee_download_attachment`
  （WebAPI V6.0，4 MiB 分块，支持断点续传）。
- **基础资料查询 FID bug 修复**（issue #28）：`BD_Currency` 等无 FID 视图的基础资料查询
  报「列名 'FID' 无效」，根因是 `QueryInput.order_string` 默认值被原样拼进 SQL；已知表单
  降级、未知表单自动去 FID 重试。
- **批量 ID 规整**：`_normalize_ids()`，解决批量 Submit/Audit/Unaudit/Delete 时列表 ID
  被静默截断为首个的问题（与 `_reconcile_batch` 配套，一个管「发对了没」，一个管「金蝶
  收全了没」）。

工具数 / 业务域数量请以 `tools/ontology/measure_tool_surface.py` 与
`tests/test_tool_count_consistency.py` 的实测结果为准，不在此手写数字。

## [0.3.0]

### 新增：AIP Logic 判断层（`aip/`）

「这一步能不能做」此前有四种答法，各长在一处（`check_*` 抛异常、
`availability()` 返回 dict、`validate_profile` 追加 errs/warns、saga 守卫
又一套）。四份实现回答同一个问题，于是可以彼此矛盾而没人发现。

现收拢成声明式、以本体为参数的纯函数：

- **一次给全部理由，不短路**——三个前置条件本来是三个来回，现在是一个。
- **「不知道」不等于「可以」**——`Decision.undetermined` 与 `allowed` 分开，
  事实不全时 `allowed` 为 `False`。旧 `availability()` 在状态未知时返回
  `enabled: True`，只读该字段的调用方会直接走下去。
- **纯函数**，不发请求、不读文件、不看时钟，故可独立运行。

新增规则 AIP-04（不可逆需人工确认）、AIP-05（二开单操作编码），
经 `Dispatcher.act` 的 `advisories` 交出。不新增 MCP 工具：
`kd_describe(what='logic')`。

### 新增：`kd-logic`，判断层可脱离模型独立运行

冷启动约 130 ms，零 token。退出码 0/1/2/3 可直接用于脚本编排。
`kd-logic serve` 可挂成本地 HTTP 端点（仅监听回环——判断层不做鉴权）。

### 破坏性变更：包结构

`base/` `aip/` `saga/` `pipeline/` `indexlayer/` `harness/` `wikiskill/`
由仓库顶层目录收进 `src/kingdee_ontology/` 命名空间。

**原因**：这些包此前**根本没被打进 wheel**（`packages` 只列了
`src/kingdee_mcp`），`pip install` 装不到；而且 `base`、`pipeline` 这类
名字也不能就这么上 PyPI，会和别的包撞名。

- `from base.ontology import …` → `from kingdee_ontology.base.ontology import …`
- `python -m base.server` → `python -m kingdee_ontology.base.server`
  （或直接用新入口 `kingdee-ontology`）
- `operation_audit` 由 `tools/ontology/` 移入包内——它被 `Dispatcher` 直接
  导入，是运行期代码，此前只靠 conftest 补 `sys.path` 才导得到。

### 变更：`pyodbc` 移出必装项

只被 4 个可选的 SQL Server 目录探查工具用到，却是全链路里唯一需要现场
编译的依赖。改为 `pip install kingdee-mcp[sql]`。导入处早已惰性并带安装
提示，不影响任何现有调用。

### 新增：离线包（内网／隔离网段）

金蝶云星空常部署在开不了外网的机器上，所以离线安装是刚需而非锦上添花。
`python3 tools/package/build_offline.py` 造两种产物：

- **`kd-logic.pyz`**（157 KB，单文件，**不用装**）——自带 PyYAML 纯 Python
  实现与本体注册表，在连 PyYAML 都没有的解释器上照样跑。
- **`wheelhouse/`**（39 个 wheel + 安装脚本）——`pip install --no-index` 装全套。
  认平台，可 `--platform win_amd64 --python-version 3.11` 跨平台造。

`MANIFEST.json` 带每个文件的 SHA256：离线传输靠 U 盘和邮件附件，传坏了要能发现。

打 tag 时由 `.github/workflows/release-offline.yml` 自动造好挂到 Release——
内网机器连 clone 都做不到，不能要求对方自己构建。

造这个包时踩到并修掉的三处：

- `zipapp` 的 `main=` 生成的入口是 `cli.main()`，**返回值被丢掉，退出码恒为 0**
  ——于是「不可以」和「事实不全」都被当成「可以」，恰好是最坏的坏法。
  改为自己写 `__main__.py`。
- 注册表原用 `Path.read_text` 读，打进 zip 后包目录不是真实目录，直接失败。
  改用 `importlib.resources`（两种情形都认），文件系统只作兜底。
- 构建时拒绝任何 `.so`/`.pyd`：zipimport 加载不了，混进去只会在没网的
  那台机器前面才炸。

### 修复：编排的起点不再只有销售订单

后端从来没这个限制——示例租户里「采购收货入库」就起于采购订单。是界面把一个
**默认值**演成了约束：预置步骤里硬编码一条 `SAL_SaleOrder` 的下推，而页面上
没有任何地方能换起点。

新增「起点」控件：补全输入框（认中文名、`form_id`、别名，56 个可选）＋
一排常用起点 chips（按可下推目标数排序，链头最可能是一件事的开头）。
换起点会清空原有步骤——两条链混在一起产出的配置过不了校验——但**可撤销**，
静默丢掉别人的活是不可接受的。认不出的输入会明确报错，而不是默默不动。

一处概念分家：`cSel`（当前位置，`commitSteps()` 会把它推到步骤链末端）与
`startNoun`（这件事从哪张单开始，加多少步都不变）此前是同一个变量。起点栏若
跟着 `cSel` 走，加一步就会显示成下游单。回归测试用变异验证过：退回旧语义后
那条测试确实失败。

### 修复：装完之后失败日志静默失效

`src/kingdee_mcp/server.py` 里 7 处 `from scripts.failure_log import FailureLogger`
全在 `try/except: pass` 里。`scripts/` 不在 wheel 里，于是**每一个 pip 安装的部署**
中，被文档称作「记忆层核心」的失败日志都悄悄不工作——不报错、不留痕，谁也不会发现。

`failure_log.py` 只依赖标准库、且被服务端在运行期导入，故移入
`kingdee_ontology/failure_log.py`。同时清掉 `server.py` 里两处早已失效的
`sys.path.insert`（绝对导入之后它们什么也不做，装成 wheel 后指向的目录压根不存在）。

**这是打包守卫自己的洞**：wheel 里装了两个包，守卫只扫了 `kingdee_ontology`。
现已扫描全部已交付的包，并新增一条专门查 `try/except` 里的不可交付导入——
用 except 兜住并不能让一个装不到的模块变得可用，只会让失效变得更难发现。
两种形态都验过：把导入改回 `scripts.` 时守卫确实报错。

### 修复：审计器 AT-07 说了一件与代码相反的事

AT-07 是**无条件**发出的，文案写死「legacy 的 5 个 push 工具尚未接入，仍无法校验
某条下推是否合法」。可它们早就接上了：`_post_raw` 的 push 分支是所有下推路径的
唯一咽喉点，在那里查注册表，并在 `KINGDEE_STRICT_LINKS=1` 时阻断；另有 6 个工具
在返回体里附带链接状态。

一条与代码相反的审计发现比不报更糟——它教人忽略审计输出。这已是第二次
（前一次是 F-1，记在 `04-audit-trail.md`），病根相同：**断言了一件没去查的事**。

现改为去 AST 里核实接线，并如实报告真正剩下的事实：默认只提示、不阻断
（这是刻意的——未登记只说明本表不全，不代表该转换关系不存在，贸然阻断会挡掉
二开账套里真实可用的下推）。

新增 `tests/test_auditor_accuracy.py`：不看措辞，只做变异测试——把咽喉点的查表
拆掉、把严格开关去掉，AT-07 的结论必须跟着升级为 warning。结论不随代码变的检查项，
不是审计，是背书。

### 新增：打包保护（`tests/test_packaging.py`）

打包缺陷对普通测试是隐形的——conftest 补了 `sys.path`，于是「只在源码树
里导得到」的模块照样过测试，装成 wheel 才 `ModuleNotFoundError`。
现分两层守：静态检查（导入来源、`sys.path` 补丁、判断层依赖闭包）+
真建 wheel 真装进干净 venv 真跑。两层都进了 CI。

---

## [0.2.4] - 2026-10-25

### Added（新增）

- **字段名修正的可见性**（issue #9）：`kingdee_save_bill` / `kingdee_validate_bill` 返回的 `auto_fixes` 现在每条都带中文字段名（`to_zh`），直接告诉用户「改了什么、这个字段是什么意思」，不再让人对着英文字段名猜。
- **无法识别字段会被报出来**（issue #9）：此前既不是有效字段、又没能自动匹配的字段会被**静默丢弃** —— 用户以为传进去了，金蝶那边根本没这个字段。现在 `validate_and_fix` 多返回一个 `unknown_fields` 列表，`save_bill` / `validate_bill` 都会把它带回结果，并给出「用 `kingdee_get_fields` 查真实字段名」的建议。字段本身**原样保留**（不做任何数据改写），由 `unknown_fields` 负责告知用户；保存失败时结果里额外带 `field_hint`，直接指向字段问题。
- **错误信息中文化**：金蝶返回的错误消息里如果出现英文字段名（`FCustId` / `FMaterialId` / `FQty` …），现在会被替换成「中文名(字段名)」形式（如 `客户(FCustId)`），错误对象新增 `raw_message` 保留原文、`field_zh` 给出字段中文名。

### Fixed（修复）

- **`kingdee_save_production_order` 补上字段名自动修正**：此前只有 `kingdee_save_bill` 走元数据纠错，生产订单保存时字段名写错会直接被金蝶拒绝、没有任何提示。现在与 `save_bill` 同口径 —— 自动修正 + 报出无法识别的字段。

---

## [0.2.3] - 2026-10-25

### Added（新增）

- **单据附件上传 / 下载**（PR #32，贡献者 @todayqaq）：新增 `kingdee_upload_attachment` 与 `kingdee_download_attachment`，支持表头/分录附件、4 MiB 分块上传、下载断点续传。依据《金蝶云星空 WebAPI 接口说明书 V6.0》实现，并经真实账套联调验证：中文文件名、约 6.3 MiB PDF 的 7 块上传/下载后字节数与 SHA-256 均一致；新增 `KINGDEE_ATTACHMENT_TIMEOUT`（附件传输默认等待 120 秒，以容纳最后一块的远端存储耗时）。
  - 上传结果不明确时返回 `outcome_unknown=true` 而非盲目重试，避免重复生成附件；日志不记录附件内容与标识。

### Fixed（修复）

- **无 FID 视图的基础资料查询**（issue #28，PR #29）：查 `BD_Currency` / `BD_AccountBook` / `BD_VOUCHERGROUP` / `BD_RateType` 等表单时报「列名 'FID' 无效」，即使 FieldKeys 里没写 FID 也报。根因是 `QueryInput.order_string` 默认值 `"FID DESC"` 被原样拼进 SQL —— 这些基础资料的查询视图本来就没有 FID 列，这是本包的默认值问题，不是金蝶限制。现对已知表单降级、未知表单自动去 FID 重试一次并记入运行时名单，仍失败则给出人话提示。

### Changed（变更）

- **对外数字与实际代码对齐**：工具数 99 → **101**、业务域 16 → **17**（新增「单据附件」域）。README / `server.json` / `SKILL.md` / 官网首页 / 官网工具列表 / 更新日志六处同步，官网工具列表的业务域卡片按代码实际分布重建为 17 个、逐域数量与 README 表格逐行一致。
- **官网接入不蒜子访问统计**（PR #17 的功能）：页脚展示访问量与访客数。
- **v0.2.2 首次真正发布到官方 MCP Registry**：`io.github.WaHaiLong/kingdee-mcp` 已上架，`server.json` 的 description 会原样被 lobehub / himcp / PulseMCP 等聚合站抓走展示。

---

## [0.2.2] - 2026-08-09

### Added（新增）

- **单据附件**：根据《金蝶云星空 WebAPI 接口说明书 V6.0》新增 `kingdee_upload_attachment` 和 `kingdee_download_attachment`，支持表头/分录附件、4 MiB 上传分块、下载续传，并避免在使用日志中记录附件内容及标识。
  - 经测试账套联调，HTTP 请求使用 `{"data":"内层 JSON 字符串"}`；已验证采购订单表头附件上传与下载内容一致，且不改变单据状态。
  - 已验证中文文件名及约 6.3 MiB PDF 的 7 块上传/下载；新增 `KINGDEE_ATTACHMENT_TIMEOUT`，附件传输默认等待 120 秒，以容纳最后一块的远端存储耗时。
- **`kingdee_query_outsource_orders`**：查询委外加工订单（`SUB_SubReqOrder`）。记录 CP 测试、封装、FT 成品测试等外协工序，支持按供应商、计划完工日、单据状态（1=开工 / 3=完工 / 6=结案 / 7=结算）、产品型号、批次号过滤。关键字段：`FNoStockInQty`（未入库在制量）、`FPlanFinishDate`（计划完工日）、`FLot.FNumber`（批次）。适用于 WIP 在制量统计、逾期分析、回货交期预测。同步在 `FORM_CATALOG` 新增 `SUB_SubReqOrder` 条目与常用过滤示例，新增 `examples/outsource-query.md`。
- **远程传输支持（HTTP / SSE / Streamable HTTP）**：`main()` 新增 `--transport`（stdio/sse/streamable-http，默认 stdio）、`--host`、`--port` 参数，并支持同名环境变量 `KINGDEE_MCP_TRANSPORT` / `KINGDEE_MCP_HOST` / `KINGDEE_MCP_PORT`。现在可将服务以 SSE（`/sse`）或 Streamable HTTP（`/mcp`）模式运行，便于部署到服务器或网关平台远程调用、免客户端安装。兼容老版本 mcp（<1.9 不支持 streamable-http 时自动回退 sse）。
- **`kingdee_query_receipts`**：查询收款单（`AR_Receivable`）。支持按客户、日期、结算方式（现金/转账/商业承兑汇票/银行承兑汇票）、核销状态过滤。关键字段：`FRealAmt`（实收金额）、`FWriteOffAmt`（已核销金额）、`FSettleTypeId.FName`（结算方式）、`FAccountId.FName`（收款账户）。适用于营收统计、回款分析、应收余额、票据占比等财务指标查询。同步完善 `FORM_CATALOG` 中 `AR_Receivable` 的字段说明、业务描述与常用过滤示例。新增 `examples/ar-receivable-query.md`。
- **6 个标准动作通用工具 + ApiDoc 全量集成**，开源 `kingdee-mcp-dev` 专家团。
- **上架官方 MCP Registry 所需元数据**：
  - 新增仓库根 `server.json`（`io.github.WaHaiLong/kingdee-mcp`，`registryType: pypi`）。
  - README 头部加入 `mcp-name: io.github.WaHaiLong/kingdee-mcp` 标记（HTML 注释形式，不影响渲染）。注册表凭该标记在 PyPI 包描述中校验包归属。
  - `publish.yml` 增加「发布 PyPI → 等待索引 → 自动 publish 到官方 MCP Registry」链路，使用 GitHub OIDC 认证，**无需任何 token 或 secret**。

### Fixed（修复）

- **会话过期漏判导致 `ctx == null` 不自愈**（issue #7）：原重登判定只认响应里带 `会话` / `session` 字样，而金蝶实际返回的是官方原生标志 `ctx == null` / `未登录` / `-10001` / `401`，导致闲置约 30 分钟后首次调用必败且不会自动重登。新增公共函数 `_is_session_expired()` 统一识别上述全部标志，替换 4 处内联判定，并在 `KNOWN_ERROR_PATTERNS` 补齐官方标志。**关键收紧**：仅对「失败响应」判定过期，避免 200 成功响应中业务字段碰巧含 `session` 字样而误触发重发 —— 杜绝 Save / Submit / Audit 等写操作被重复提交。新增回归测试 `TestSessionExpiryDetection` 共 8 例（含防重复提交守卫用例）。
- **批量 Submit/Audit/Unaudit/Delete 不再静默丢单**（issue #8）：`_post_raw` 遇到列表形式的 `Ids` 时原本只取首个（`ids[0]`），其余 ID **被静默丢弃且接口仍返回 `success: true`**。用户批量反审核 11 张单据，实际只有 1 张生效。现改为按金蝶 WebAPI 约定逗号拼接（`{"Ids":"100,101,102"}`，与 `CancelAssign` / `ExecuteOperation` 同一约定），并抽出纯函数 `_normalize_ids()`（自动去空白、去重保序，空 ID 显式报错而非发空请求）。
  - `kingdee_submit_bills` / `kingdee_audit_bills` / `kingdee_unaudit_bills` / `kingdee_delete_bills` 此前已改为逐张调用绕开了该问题，但**根因未除**：`kingdee_submit_production_orders` / `kingdee_audit_production_orders` 仍在直接传列表，批量提交生产订单时同样只有首张生效。本次从根上修掉。
- **批量操作新增「提交数 vs 成功数」对账**（issue #8 的另一半）：`_result_status()` 原先只看金蝶返回的 `IsSuccess`，从不核对实际生效数量 —— 金蝶少处理了单据仍会报成功。现新增可选参数 `requested_ids`，传入后与 `SuccessEntitys` 对账，发现漏单则把 `success` 置为 `False` 并列出 `missing_ids`。不传该参数时行为完全不变，老调用方零影响。
- `kingdee_query_permission` 重复注册问题；`__init__.py` 版本号与 `pyproject.toml` 对齐。

### Fixed（修复 · 文档）

- **README 工具数量少报**：功能特性与工具列表长期写「87/88 个工具」，实测 `server.py` 已注册 97 个（本次两个新工具后为 99 个）。已按实际数量修正。
- **对外清单数字与代码对不上（发版前拦下）**：`server.json` 的 `description` 仍写 `87 tools, 13 domains`，而这份文件要提交到官方 MCP Registry，并被 lobehub / himcp / PulseMCP 等聚合站原样抓取展示 —— 照此发布等于对外少报 12 个工具。同时 README 顶部写「99 个工具」，下方业务域表格逐行相加却只有 87，表格自身也没对上。现已核对 `server.py` 实际注册的 99 个工具（无重名），重新归入 16 个业务域并逐行校正数量；`server.json`、README 顶部声明、业务域表格三处统一为 **99 工具 / 16 业务域**。
- **新增发版元数据一致性回归测试**（`tests/test_tool_count_consistency.py`，9 例，已接入 CI）：锁死「代码实际工具数 == README 声明 == README 表格合计 == `server.json` description」「业务域数量三处一致」「`pyproject.toml` / `__init__.py` / `server.json` 顶层与 `packages[0]` 四处版本号一致」「description ≤ 100 字符（官方 Registry 硬限制）」「第三方非官方声明不得被删」「PyPI 包名与 `pyproject.toml` 一致」。这类错误不会让程序崩，功能测试永远发现不了；版本号漏改一处更是要等 tag 已经推出去、PyPI 拒收时才暴露，回滚代价高。

### Changed（变更）

- **CI 补跑回归测试**：`harness-check.yml` 此前只跑 `tests/test_server.py`，导致 issue #13 的表名一致性回归测试（`test_db_tables_consistency.py`）虽已入库却从未在 CI 中执行 —— 表名被改回去 CI 依然是绿的。现新增独立步骤，显式运行全部「对应真实用户 issue」的回归测试。

---

## [0.2.1] - 2026-08-05

### Fixed（修复 · 文档）

- **修正改用账号密码登录的原因说明**：README「从 0.1.0 升级的破坏性变更」与 `server.py` `_login` docstring 原写为「为避免第三方应用授权的 APP 白名单限制、公有云/私有云通用」，该原因有误。正确原因：账号密码(ValidateUser) 以真实用户身份执行 WebAPI、携带该用户自身业务权限（含数据权限控制）；第三方应用授权(LoginByAppSecret) 以应用身份登录、不携带真实用户权限，报表等依赖数据权限的查询会受应用授权范围限制。无功能/行为变更。

---

## [0.2.0] - 2026-08-05

### Changed（变更）

- **版本对齐与重新发版**：本地源码自 2026-07-19 起已包含 86 工具、账号密码登录、SQL Server 探查等大量更新，但 PyPI 上仍停留在 2026-03-25 发布的旧 `0.1.0`（仅 13 工具 + AppSecret 登录）。本版将 PyPI 包与源码对齐，统一为 `0.2.0`。
- **README / 文档同步**：PyPI 展示的 README 已更新为 86 工具 + 账号密码登录的说明（此前 PyPI 长期展示旧版文档）。

### Added（新增 · 相对 PyPI 旧 0.1.0）

- 86 个工具（生产 / 成本 / 资产 / 审计 / 采购 / 销售 / 库存 / 工作流 / 元数据 / 系统 / 统计等 13 大业务域）。
- 4 个 SQL Server 探查工具（`kingdee_discover_tables` / `kingdee_discover_columns` / `kingdee_describe_table` / `kingdee_discover_metadata_candidates`），需配置 `MCP_SQLSERVER_*`。
- 元数据动态查询（`get_bill_template` / `validate_bill` / `refresh_metadata`），元数据本地缓存。
- MCP 使用日志系统、错误自描述、强制 HTTP/1.1 解决金蝶 WebAPI 偶发 502。
- **财务报表查询工具 `kingdee_query_report`**：通过专用 `GetSysReportData`（KDSReportAPIService）端点查询总账/财务报表，与单据查询（ExecuteBillQuery）分属不同服务。已实测确认科目余额表 `GL_RPT_AccountBalance`、总账账龄分析表 `GL_AgingSchedule`（无 `RPT_` 前缀）；其余报表 formId 待逐张查证。内层过滤参数（账簿/年度/期间/科目等）由调用方按账套透传，避免臆造字段名。

### Breaking（破坏性变更）

- **登录方式变更**：移除第三方应用授权登录（`LoginByAppSecret`），改为仅账号密码（`ValidateUser`）。旧环境变量 `KINGDEE_APP_ID` / `KINGDEE_APP_SEC` **已失效**，须改用 `KINGDEE_PASSWORD`。详见 README「从 0.1.0 升级的破坏性变更」。

### Fixed（修复 · 文档）

- README「常见问题」新增 `uvx` 启动报 `No module named 'mcp.server.fastmcp'` 的排查（清缓存或改用 `pip install` + `python -m kingdee_mcp.server`）。

---

## [0.1.0] - 2026-07-19

### Added（新增）

- **13 大业务域、共 86 个工具**，覆盖生产制造、成本核算、固定资产、审计合规、采购、销售、库存、工作流审批、基础资料、元数据探查、系统查询等。
- **生产制造模块**：生产订单查询/保存/提交/审核、MRP 运算结果、生产计划、生产汇报、生产入库、生产领料下推（`kingdee_query_production_*`、`kingdee_save_production_order`、`kingdee_push_production_*` 等 12 个）。
- **成本核算模块**：材料成本、成本计算、成本趋势、实际 vs 标准成本对比、完工产品成本、成本调整单等（`kingdee_query_material_cost`、`kingdee_query_cost_calculation`、`kingdee_save_cost_adjustment` 等 12 个）。
- **固定资产模块**：资产卡片、资产折旧、资产盘点、资产调拨、资产新增（`kingdee_query_fixed_asset`、`kingdee_save_asset` 等 6 个）。
- **审计合规模块**：操作日志、变更日志、审核日志、复合「新建并审核」「下推并审核」工作流（`kingdee_query_operation_logs`、`kingdee_query_change_log`、`kingdee_create_and_audit`、`kingdee_push_and_audit` 等 7 个）。
- **元数据动态查询**：`kingdee_get_bill_template`（取已验证单据骨架）、`kingdee_validate_bill`（保存前校验，不真正落库）、`kingdee_refresh_metadata`（强制刷新），元数据落盘缓存到 `~/.workbuddy/kingdee_metadata_cache/`。
- **SQL Server 探查工具 4 个**：`kingdee_discover_tables`、`kingdee_discover_columns`、`kingdee_describe_table`、`kingdee_discover_metadata_candidates`（配置 `MCP_SQLSERVER_*` 环境变量后可用）。
- **MCP 使用日志系统**：记录工具调用，便于审计与排查。
- **权限架构设计方案**文档（`docs/permission-architecture.md`）。
- **TEST_GUIDE 与生产工作流 e2e** 测试，回归网覆盖核心链路。

### Changed（变更）

- **登录方式改为仅账号密码（ValidateUser）**，移除第三方应用授权（原 `LoginByAppSecret`）。配置只需 `KINGDEE_SERVER_URL`、`KINGDEE_ACCT_ID`、`KINGDEE_USERNAME`、`KINGDEE_PASSWORD` 四项，**不再需要 AppID / AppSecret**。
- `kingdee_view_bill` 返回结果精简，只保留常用字段，降低 token 消耗。
- `kingdee_query_bills` 等查询类工具的过滤与返回结构优化。
- 批量操作（提交/审核/反审核/删除）真正批量化，减少循环请求。
- 错误自描述：接口失败时返回更可读的中文错误，便于 AI 与用户定位。
- 强制使用 HTTP/1.1 解决金蝶 WebAPI 偶发 502 问题。
- 文档/示例/脚本/测试整体同步。

### Fixed（修复）

- **销售报价单（SAL_Quotation）保存报"含税单价不能小于等于0"的真正根因 = 字段顺序**：本二开账套金蝶 Save 对字段顺序敏感，`FQUOTATIONFIN`（财务信息，含结算币别/含税标志）必须排在 `FQUOTATIONENTRY`（分录）之前，否则分录单价被算成 0。`kingdee_save_bill` 新增防御性排序（所有非 ENTRY 键统一前置），`BILL_TEMPLATES` 补 `FQUOTATIONFIN` 并置于 ENTRY 之前。
- 修正 `kingdee_push_bill` API 格式、`_post_raw` 入参与生产下推（`push_production`）参数。
- 补全若干缺失函数，修复批量操作的一致性。

### Removed（移除）

- 第三方应用授权登录（`LoginByAppSecret`）及相关 `APP_ID` / `APP_SEC` 环境变量、配置项。

---

## 历史提交摘要（按时间倒序，供溯源）

| 提交 | 说明 |
|------|------|
| `f58c2a7` | fix: 销售报价单 Save 字段顺序校正 + 新增 API 中心快照 |
| `c3fbaf5` | feat: 登录改为仅账号密码(ValidateUser)，移除第三方应用授权 |
| `a5b17e5` | chore: 忽略运行时日志/工具缓存/记忆目录/临时文件 |
| `6145af1` | test: 新增 TEST_GUIDE 和生产工作流 e2e |
| `a61d845` | chore: 同步文档/示例/脚本/测试 |
| `5c742a0` | feat: 元数据动态查询 + view 结果精简 |
| `6b7b58d` | docs: 添加权限架构设计方案 |
| `529a55e` | feat: 添加 MCP 使用日志系统 |
| `5bbc744` | fix: 批量操作真批量化 + 补全缺失函数 + 修正 push_production 参数 |
| `04d4eba` | feat: 新增 MRP/生产计划/生产汇报查询工具 |
| `96f7f93` | feat: 新增审计合规模块 API |
| `354e339` | feat: 新增生产、成本、资产管理等模块 API |
| `e034152` | feat: 复合工作流工具 + 错误自描述 + e2e 回归网 |
| `6b754c3` | fix: 强制使用 HTTP/1.1 解决金蝶 WebAPI 502 问题 |
| `30b2a19` | feat: 新增 4 个 SQL Server 探查工具 |

完整历史见 [GitHub Commits](https://github.com/WaHaiLong/KingdeeMCP/commits/main)。
