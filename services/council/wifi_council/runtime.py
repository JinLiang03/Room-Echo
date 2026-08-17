"""Runtime wiring: provider from env, orchestrator, scheduler, store."""

from __future__ import annotations

from pathlib import Path

from wifi_contracts import ProviderHealth

from .audit import CouncilAuditLog, CouncilStore
from .config import CouncilConfig, provider_from_env
from .fusion import FusionAssembler
from .orchestrator import CouncilOrchestrator
from .policy import PolicyArbiter
from .provider import AgentProvider, MockAgentProvider, OpenAIAgentProvider
from .scheduler import CouncilScheduler


def build_provider(
    config: CouncilConfig,
    provider_name: str | None = None,
    *,
    demo_scenario: bool = False,
) -> AgentProvider:
    name = provider_name or provider_from_env()
    if name == "openai":
        return OpenAIAgentProvider(config)
    return MockAgentProvider(config, demo_scenario=demo_scenario)


class CouncilRuntime:
    def __init__(
        self,
        config: CouncilConfig | None = None,
        *,
        provider: AgentProvider | None = None,
        audit_path: Path | None = None,
    ) -> None:
        self.config = config or CouncilConfig()
        self.provider = provider or build_provider(self.config)
        self.policy = PolicyArbiter(self.config)
        self.fusion = FusionAssembler(self.config)
        self.orchestrator = CouncilOrchestrator(
            self.provider,
            self.config,
            policy=self.policy,
            fusion=self.fusion,
        )
        self.audit = (
            CouncilAuditLog(audit_path) if audit_path is not None else None
        )
        self.store = CouncilStore(self.audit)
        self.scheduler = CouncilScheduler(
            self.orchestrator,
            self.store,
            self.config,
            audit=self.audit,
        )

    def health(self) -> list[ProviderHealth]:
        """Active provider health plus an OpenAI key-presence probe."""
        active = self.provider.health()
        openai = (
            OpenAIAgentProvider(self.config).health()
            if self.provider.name != "openai"
            else active
        )
        return [active, openai]


_runtime: CouncilRuntime | None = None


def get_runtime() -> CouncilRuntime:
    global _runtime
    if _runtime is None:
        _runtime = CouncilRuntime()
    return _runtime
