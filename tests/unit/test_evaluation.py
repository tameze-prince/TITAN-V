from titan.runtime.contracts import AgentModelOutput
from titan.runtime.evaluation import evaluate_execution


def test_quality_gate_rejects_missing_tool_execution_evidence() -> None:
    output = AgentModelOutput(
        summary="The project has been created.",
        result={"tool_calls": [], "tool_results": []},
        artifact_markdown="# Project created",
    )

    report = evaluate_execution(
        output=output,
        artifact_markdown=output.artifact_markdown,
        require_tool_execution=True,
    )

    assert report.passed is False
    assert report.checks["tool_execution_present"] is False


def test_quality_gate_accepts_correlated_completed_tool_execution() -> None:
    output = AgentModelOutput(
        summary="Inspected the workspace.",
        result={
            "tool_calls": [
                {"kind": "tool_call", "call_id": "call-1", "name": "workspace.list"}
            ],
            "tool_results": [
                {
                    "kind": "tool_result",
                    "call_id": "call-1",
                    "name": "workspace.list",
                    "status": "COMPLETED",
                    "output": {"entries": []},
                }
            ],
        },
        artifact_markdown="# Workspace inspection",
    )

    report = evaluate_execution(
        output=output,
        artifact_markdown=output.artifact_markdown,
        require_tool_execution=True,
    )

    assert report.passed is True
    assert report.checks["tool_execution_present"] is True
