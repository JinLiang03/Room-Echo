# Phase 07：多 Agent 争论、Policy Arbiter 与审计

## Role

你是多 Agent 系统工程师。实现有限、结构化、可审计的争论，使 Agent 增加替代解释覆盖和越权检测，而不是用投票制造传感器可信度。

## Read first

`docs/AGENT_COUNCIL.md`、`docs/DATA_CONTRACTS.md`、`docs/ACCEPTANCE_TESTS.md`、Phase 06 EvidencePacket/quality code。联网时核对 OpenAI Agents SDK 与 Structured Outputs 官方当前文档。

## Goal

实现 Mock/OpenAI 两种 provider、六个角色、两轮质询上限、确定性 Policy Arbiter、异步调度、超时降级、审计日志与 API。

## Deliverables

1. `AgentProvider` 协议及 `MockAgentProvider`、`OpenAIAgentProvider`。
2. 角色：DataQuality、Motion、Occupancy、Depth、RedTeam、Fusion。
3. Prompt registry：公共 prompt + 角色增量；每份有 version/hash；内容遵循 `AGENT_COUNCIL.md`。
4. 使用 Pydantic output types/Structured Outputs；拒绝自由文本 JSON parsing 作为主路径。
5. Orchestrator 状态机：seal/gate/propose/cross-examine/respond/policy/synthesize/commit。
6. 确定性 `PolicyArbiter`：引用、hash、数值、禁区、单 RX、profile、挑战和置信不变量。
7. Scheduler：一个 active cycle + 一个 latest pending；过期结果不能覆盖 current。
8. Call budget：默认每周期最多 6 次；Agent 超时重试 1 次；15 s hard deadline。
9. `CouncilResult` 与 audit events；只保存短 reasoning summary，不要求或展示隐藏思维链。
10. API：cycle detail、claims、challenges、policy rejections、provider health、usage summary。

## Provider behavior

- 默认 `AGENT_PROVIDER=mock`，CI 不访问网络。
- OpenAI key 只从服务端环境读取；缺 key 自动健康告警并回退 mock/baseline，绝不把 key 发到 Web。
- Model 名称来自环境/config 并出现在 provenance；不要硬编码未经用户选择的昂贵模型。
- 同一 EvidencePacket 可缓存相同 role/prompt/model 输出；缓存不能跨 schema/prompt/model/version。
- 不给 Agent raw CSI arrays、ground truth、真实 MAC 或无关历史周期。

## Mock behavior

Mock 必须是真正可测的模拟 Council，而不是全部同意：

- 对 interference scenario 提出至少一个 material confound。
- 对 single RX depth 主张 abstain。
- 对 invalid evidence ref 产生可控坏输出 fixture，验证 Policy 拒绝。
- 固定 seed 与模板版本，重复运行稳定。

## Policy rules

实现并 property-test：

```text
display_confidence <= model_support <= sensor_confidence_cap
agent_count does not affect confidence
agreement does not affect confidence
unavailable cannot be narrated as present
all accepted evidence_refs resolve within current evidence_hash
```

对“墙后有人”“发现两个人”“距离 3.2 米”“人体姿态”“心率”等越权主张直接拒绝并公开 reason code。

## Tests

- 1/3/6 Agent confidence identical。
- 100% agreement 不抬分；重复证据不抬分。
- single RX、mismatch、unavailable、OOD、stale 的结果。
- 非法 schema、虚构 ref、旧 hash、新造数值、越权语言被拒绝。
- retry、timeout、全 provider offline、out-of-order cycle。
- Mock full debate snapshot test；OpenAI provider 只做 opt-in integration test，不进默认 CI。
- Fusion 输出的所有数值能逐字段追溯到 approved input。

## Acceptance gate

```bash
AGENT_PROVIDER=mock make test-council
AGENT_PROVIDER=mock make replay-council REPLAY=data/fixtures/walk_through
make test-confidence-invariants
```

若用户环境已有 API key，可另运行 opt-in smoke，并只记录 model/latency/status/usage，不记录 key。没有 key 不阻塞本阶段。

## Completion

通过后记录 provider、prompt versions、confidence tests 和 audit artifact；勾选 Phase 07。停止，不实现 Web。

