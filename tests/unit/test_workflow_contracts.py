from uuid import uuid4

from titan.workflows.contracts import WorkflowInput, WorkflowResult


def test_workflow_input_is_immutable_and_typed() -> None:
    value = WorkflowInput(
        workflow_id=uuid4(),
        project_id=uuid4(),
        task_ids=(uuid4(),),
    )

    assert isinstance(value.task_ids, tuple)
    assert value.workflow_id
    assert value.project_id


def test_workflow_result_defaults_to_empty_tasks() -> None:
    value = WorkflowResult(workflow_id=uuid4(), status="COMPLETED")

    assert value.completed_task_ids == ()
    assert value.run_id is None
