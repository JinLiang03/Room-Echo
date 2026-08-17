# Phase 01：工程骨架、契约与本地启动

## Role

你负责建立一个可长期迭代的 monorepo 骨架，并把 schema、命令、测试和状态管理先固化。此阶段不实现 CSI 算法或 Agent 业务。

## Read first

`AGENTS.md`、`PROJECT_INDEX.yaml`、`STATE.md`、`TASKS.md`、`docs/PRODUCT_SPEC.md`、`docs/ARCHITECTURE.md`、`docs/DATA_CONTRACTS.md`。

## Goal

创建工程目录、Python/Node 工具链、canonical Pydantic contracts、TS 类型生成、健康 API、空 Web 壳、统一命令和确定性 fixture，使后续所有阶段能独立测试。

## Deliverables

1. 创建 `firmware/`、`services/{collector,sensing,council,api}`、`apps/web`、`packages/contracts`、`configs`、`data/{fixtures,calibration,raw,derived}`、`tests`、`scripts`。
2. Python：`pyproject.toml`，锁定并记录依赖；配置 ruff、mypy、pytest、coverage。
3. Web：React + TS + Vite，strict TS，Vitest；不引入大型 UI 框架。
4. `packages/contracts`：实现 SourceManifest、NormalizedCsiFrame、FeatureWindow、SignalTriplet、EvidencePacket、AgentClaim、AgentChallenge、CouncilResult、WebSocketEnvelope。
5. 从 Pydantic/JSON Schema 自动生成前端类型；提供 drift check。
6. FastAPI `/healthz` 返回版本、mode 和 component health；Web 显示连接状态和 placeholder。
7. `templates/.env.example` 复制为根 `.env.example`，不得创建真实 key。
8. `Makefile` 或同等 task runner，至少有 `setup`、`dev`、`test`、`lint`、`typecheck`、`build`、`verify-contracts`。
9. `scripts/generate_fixtures.py` 用固定 seed 生成最小合法 frame/window/triplet/evidence；fixture 标 `source_mode=mock`。
10. 本地开发说明和架构决策 `docs/adr/0001-monorepo-and-contracts.md`。

## Implementation constraints

- Pydantic 是结构事实源；JSON Schema 和 TypeScript 从它生成。
- 金额/传感概率等浮点使用明确范围校验；概率和用 model validator 校验。
- `final_claim_confidence/display_confidence` 上限不变量必须在 model validator 与 property test 中存在。
- ID、timestamp、schema version、source mode 不可省略。
- 健康 API 不泄露环境变量或主机绝对路径。
- Docker Compose 可选；不要让串口 Live 强依赖容器。

## Tests

- 合法 fixture 在 Python、JSON Schema、TS 三处通过。
- 缺字段、额外字段、概率和错误、置信上限错误、未知 source mode 被拒绝。
- 同一 fixture JSON round-trip 稳定。
- `/healthz` smoke test。
- Web typecheck、unit test、production build。

## Acceptance gate

运行并记录实际命令：

```bash
python -m ruff check .
python -m mypy services packages
python -m pytest tests/contracts tests/api
npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
npm --prefix apps/web run test
npm --prefix apps/web run build
make verify-contracts
```

若工具链命令与环境不同，建立等价命令并记录。启动 API 与 Web，确认页面能显示健康状态。

## Completion

验收通过后更新 `STATE.md`：版本、命令、结果、未解决警告；勾选 Phase 01。不要实现 Phase 02。

