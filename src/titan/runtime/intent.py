from typing import Any

from pydantic import BaseModel, Field


class IntentRepresentation(BaseModel):
    problem: str = ""
    target_users: list[str] = Field(default_factory=list)
    desired_outcome: str = ""
    constraints: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    research_questions: list[str] = Field(default_factory=list)
    candidate_deliverables: list[str] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)


class IntentCompileResult(BaseModel):
    representation: IntentRepresentation
    provider: str
    model: str
    usage: dict[str, Any] = Field(default_factory=dict)


class IntentCompiler:
    def __init__(self, provider, model: str) -> None:
        self.provider = provider
        self.model = model

    async def compile(
        self,
        *,
        raw_intent: str,
        project_context: dict[str, Any] | None = None,
        user_context: dict[str, Any] | None = None,
    ) -> IntentCompileResult:
        if not raw_intent.strip():
            raise ValueError("Intent cannot be empty")

        request = {
            "raw_intent": raw_intent,
            "project_context": project_context or {},
            "user_context": user_context or {},
        }
        response = await self.provider.generate(
            type("IntentRequest", (), {
                "system_prompt": (
                    "You are TITAN's Intent Compiler. Convert the user's raw intent "
                    "into the exact structured IntentRepresentation schema. "
                    "Do not invent facts. Mark missing information as unknowns or assumptions. "
                    "Identify constraints, risks, research questions, deliverables and capabilities."
                ),
                "user_prompt": str(request),
                "model": self.model,
                "metadata": {"component": "intent-compiler"},
            })(),
            IntentRepresentation,
        )
        return IntentCompileResult(
            representation=response.parsed,
            provider=response.provider,
            model=response.model,
            usage=response.usage,
        )


def local_compile_intent(raw_intent: str) -> IntentRepresentation:
    cleaned = raw_intent.strip()
    return IntentRepresentation(
        problem=cleaned[:500],
        desired_outcome=cleaned,
        unknowns=["Detailed target users and constraints have not yet been verified."],
        assumptions=["The raw request describes the desired outcome at a high level."],
        research_questions=["Who are the target users?", "What constraints must the solution satisfy?"],
        candidate_deliverables=[cleaned],
        required_capabilities=["analysis", "structured-output"],
    )
