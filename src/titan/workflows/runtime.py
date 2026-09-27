import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from titan.workflows.contracts import WorkflowInput, WorkflowResult

with workflow.unsafe.imports_passed_through():
    from titan.runtime.scheduler import DependencyAwareScheduler, TaskSchedulingProfile
    from titan.workflows.activities import (
        mark_workflow_completed,
        mark_workflow_failed,
        mark_workflow_started,
        orchestrate_task,
        attempt_automatic_recovery,
    )


RETRY_POLICY = RetryPolicy(initial_interval=timedelta(seconds=1), maximum_attempts=3)


@workflow.defn
class TitanWorkflow:
    @workflow.run
    async def run(self, request: WorkflowInput) -> WorkflowResult:
        temporal_workflow_id = workflow.info().workflow_id
        temporal_run_id = workflow.info().run_id

        run_id: str = await workflow.execute_activity(
            mark_workflow_started,
            args=(
                request.workflow_id,
                temporal_workflow_id,
                temporal_run_id,
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RETRY_POLICY,
        )

        completed_task_ids: list[str] = list(request.precompleted_task_ids)
        schedule = DependencyAwareScheduler().build(
            request.task_ids,
            request.dependencies,
            task_agents=request.task_agents,
            agent_capacities=request.agent_capacities,
            task_profiles=tuple(
                TaskSchedulingProfile(
                    task_id=profile.task_id,
                    risk_level=profile.risk_level,
                    minimum_quality_tier=profile.minimum_quality_tier,
                    estimated_cost=profile.estimated_cost,
                    expected_duration_ms=profile.expected_duration_ms,
                    priority=profile.priority,
                    provider_available=profile.provider_available,
                )
                for profile in request.task_profiles
            ),
            max_project_cost=request.max_project_cost,
            precompleted_task_ids=request.precompleted_task_ids,
        )

        try:
            for wave in schedule.waves:
                results = await asyncio.gather(
                    *(
                        workflow.execute_activity(
                            orchestrate_task,
                            args=(request.workflow_id, task_id, run_id),
                            start_to_close_timeout=timedelta(seconds=60),
                            retry_policy=RETRY_POLICY,
                        )
                        for task_id in wave
                    ),
                    return_exceptions=True,
                )
                failures = [
                    result
                    for result in results
                    if isinstance(result, BaseException)
                ]
                if failures:
                    raise failures[0]
                completed_task_ids.extend(wave)

            await workflow.execute_activity(
                mark_workflow_completed,
                args=(
                    request.workflow_id,
                    run_id,
                    tuple(completed_task_ids),
                ),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RETRY_POLICY,
            )

            return WorkflowResult(
                workflow_id=request.workflow_id,
                status="COMPLETED",
                completed_task_ids=tuple(
                    task_id
                    for task_id in request.task_ids
                    if task_id in set(completed_task_ids)
                ),
                execution_waves=schedule.waves,
                estimated_schedule_cost=schedule.estimated_cost,
                estimated_makespan_ms=schedule.estimated_makespan_ms,
                run_id=run_id,
            )
        except Exception as exc:
            await workflow.execute_activity(
                mark_workflow_failed,
                args=(request.workflow_id, run_id, str(exc)),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RETRY_POLICY,
            )
            await workflow.execute_activity(
                attempt_automatic_recovery,
                args=(request.workflow_id, run_id, str(exc)),
                start_to_close_timeout=timedelta(seconds=120),
                retry_policy=RETRY_POLICY,
            )
            raise
