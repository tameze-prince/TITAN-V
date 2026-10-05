"""Opt-in real-provider vertical slice for the first TITAN V product validation.

Run manually only after configuring a real provider:

    TITAN_E2E_REAL=1 \
    TITAN_MODEL_PROVIDER=openai \
    TITAN_OPENAI_API_KEY=... \
    pytest -q tests/e2e/test_real_project_execution.py -vv

The test is intentionally excluded from normal CI because it requires a paid
external model credential and validates behavior rather than deterministic
invariants.
"""

import os
from pathlib import Path

import pytest

from titan.config import settings
from titan.runtime.contracts import AgentTaskContext
from titan.runtime.service import AgentRuntime
from titan.runtime.tools import ToolCall


_real_provider_ready = (
    (
        settings.model_provider == "openai"
        and bool(settings.openai_api_key)
    )
    or (
        settings.model_provider == "nvidia"
        and bool(settings.nvidia_api_key)
    )
)

pytestmark = pytest.mark.skipif(
    os.getenv("TITAN_E2E_REAL") != "1" or not _real_provider_ready,
    reason=(
        "Real-provider E2E requires TITAN_E2E_REAL=1, "
        "plus a configured OpenAI or NVIDIA provider."
    ),
)


@pytest.mark.asyncio
async def test_real_provider_builds_and_tests_a_workspace_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "workspace_root", str(tmp_path / "workspaces"))

    runtime = AgentRuntime()
    task_id = "11111111-1111-4111-8111-111111111111"
    project_id = "22222222-2222-4222-8222-222222222222"
    run_id = "33333333-3333-4333-8333-333333333333"

    context = AgentTaskContext(
        task_id=task_id,
        run_id=run_id,
        project_id=project_id,
        title="Build a minimal Python project",
        objective=(
            "Create a tiny Python project in the assigned workspace. "
            "Create app.py with an add(a, b) function and test_app.py using Python's "
            "standard-library unittest. Use sandbox.exec to create or modify the files "
            "and run the tests before reporting completion. The workspace must contain "
            "both files and the test suite must pass. Do not merely describe code; "
            "actually create it and execute it."
        ),
        risk_level="R2",
    )

    result = await runtime.execute(
        context,
        agent_name="engineering-executor",
    )

    assert result.provider == settings.model_provider
    assert result.status == "COMPLETED"

    workspace = runtime.workspace_manager.ensure(project_id, task_id).root
    app_file = workspace / "app.py"
    test_file = workspace / "test_app.py"
    assert app_file.is_file()
    assert test_file.is_file()

    tool_calls = result.output.result.get("tool_calls", [])
    assert any(call.get("name") == "sandbox.exec" for call in tool_calls)

    verification = await runtime.execute_tool(
        ToolCall(
            name="sandbox.exec",
            arguments={
                "command": ["python", "-m", "unittest", "discover", "-v"],
            },
        ),
        context,
        workspace=workspace,
        agent_name="engineering-executor",
    )

    assert verification.status == "COMPLETED"
    assert verification.output["exit_code"] == 0
    assert "OK" in verification.output["stdout"]
