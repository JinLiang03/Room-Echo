# 文档入口

本文是仓库文档的导航页。它不替代各专题文档，也不移动或删除历史材料；评测者可以从这里区分当前规范、运行说明和阶段性记录，避免把旧快照误当成最新架构。

## 先读这四份

1. [产品与真实用户](PRODUCT_SPEC.md)：为谁而做、核心体验与非目标。
2. [系统架构](ARCHITECTURE.md)：Source、信号链、Council、API/MCP 与 Web 的当前实现。
3. [Agent Council](AGENT_COUNCIL.md)：七角色、证据边界、Provider、Policy 与调用预算。
4. [验收测试](ACCEPTANCE_TESTS.md)：可复现门禁、已验证范围和硬件待验证项。

## 开发、运行与部署

- [快速开始](QUICKSTART.md)
- [开发说明](DEVELOPMENT.md)
- [公网 Replay 部署](DEPLOY_PUBLIC_REPLAY.md)
- [演示脚本](DEMO_SCRIPT.md)
- [故障排查](TROUBLESHOOTING.md)
- [贡献指南](CONTRIBUTING.md)

## Agent、数据与体验规范

- [Agent Council](AGENT_COUNCIL.md)
- [数据合约](DATA_CONTRACTS.md)
- [数据端口](DATA_PORTS.md)
- [Web UX](WEB_UX_SPEC.md)
- [数字推断场设计](DIGIT_INFERENCE_FIELD_DESIGN.md)
- [隐私](PRIVACY.md)与[限制](LIMITATIONS.md)

## 硬件与标定

- [硬件和标定总览](HARDWARE_AND_CALIBRATION.md)
- [Live 设置](LIVE_SETUP.md)
- [标定协议](CALIBRATION.md)
- [Live Demo BOM](BOM_LIVE_DEMO.md)
- [线协议](WIRE_PROTOCOL.md)
- [固件源码审查](FIRMWARE_SOURCE_REVIEW.md)

## 审计与设计决策

- [架构对齐](ARCHITECTURE_ALIGNMENT.md)
- [开源审计](OPEN_SOURCE_AUDIT.md)
- [`docs/adr/`](adr/)：不可变设计决策及其理由。

## 阶段性记录

以下文件保留评测和交接时点，不是所有字段的当前规范；若与上述当前文档冲突，以当前源码、`STATE.md` 和专题规范为准。

- [2026-08-08 评估快照](ASSESSMENT_2026-08-08.md)
- [交接快照](HANDOFF.md)
