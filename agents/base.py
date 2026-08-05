import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import str


class AgentStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Finding:
    severity: str  # critical | high | medium | low | info
    category: str  # secret | cve | smell | coverage | etc.
    message: str
    file: str | None = None
    line: int | None = None
    suggestion: str | None = None


@dataclass
class AgentResult:
    agent: str
    status: AgentStatus
    findings: list[Finding] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    pr_url: str | None = None
    error: str | None = None

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "critical")

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "high")


class BaseAgent(ABC):
    name: str

    @abstractmethod
    async def run(
        self,
        *,
        event_type: str,
        payload: dict,
        installation_id: int,
    ) -> AgentResult:
        """Execute the agent and return results."""

    def _result(self, status: AgentStatus, **kwargs) -> AgentResult:
        return AgentResult(agent=self.name, status=status, **kwargs)

    def _skip(self, reason: str = "") -> AgentResult:
        return AgentResult(
            agent=self.name, status=AgentStatus.SKIPPED, actions=[reason] if reason else []
        )
