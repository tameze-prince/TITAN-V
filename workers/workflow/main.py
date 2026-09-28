import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from titan.config import settings
from titan.workflows.activities import (
    mark_workflow_completed,
    mark_workflow_failed,
    mark_workflow_started,
    attempt_automatic_recovery,
    orchestrate_task,
)
from titan.workflows.runtime import TitanWorkflow


logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(level=settings.log_level)

    client = await Client.connect(
        settings.temporal_target,
        namespace=settings.temporal_namespace,
    )

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[TitanWorkflow],
        activities=[
            mark_workflow_started,
            orchestrate_task,
            mark_workflow_completed,
            mark_workflow_failed,
            attempt_automatic_recovery,
            mark_workflow_approval_expired,
        ],
    )

    logger.info("Starting TITAN workflow worker on %s", settings.temporal_task_queue)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
