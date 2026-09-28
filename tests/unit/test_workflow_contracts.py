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


def test_workflow_input_carries_human_approval_gate_tasks() -> None:
    task_id = str(uuid4())
    value = WorkflowInput(
        workflow_id=str(uuid4()),
        project_id=str(uuid4()),
        task_ids=(task_id,),
        approval_task_ids=(task_id,),
    )

    assert value.approval_task_ids == (task_id,)
    assert value.approval_timeout_seconds == 86_400
