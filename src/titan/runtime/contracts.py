from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field


class AgentContract(BaseModel):
    name: str
    role: str
    version: str = "1.0.0"
    instructions: str
    capabilities: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    risk_ceiling: str = Field(default="R1", pattern=r"^R[0-4]$")
    model: str = "local"
    minimum_quality_tier: int = 1
    max_concurrency: int = Field(default=1, ge=1, le=64)
    scheduling_priority: int = Field(default=0, ge=-100, le=100)


@dataclass(frozen=True, slots=True)
class AgentTaskContext:
    task_id: str
    run_id: str
    project_id: str
    title: str
    objective: str
    risk_level: str
    inputs: dict[str, Any] = field(default_factory=dict)


class AgentModelOutput(BaseModel):
    summary: str = Field(min_length=1, max_length=20_000)
    result: dict[str, Any] = Field(default_factory=dict)
    artifact_markdown: str = ""


class AgentExecutionResult(BaseModel):
    task_id: str
    agent_name: str
    agent_version: str
    provider: str
    model: str
    status: str
    output: AgentModelOutput
    duration_ms: int = 0
    usage: dict[str, Any] = Field(default_factory=dict)
    evaluation: dict[str, Any] = Field(default_factory=dict)
