from __future__ import annotations

import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from worldline_api.config import settings
from worldline_api.workflows import (
    BuildMainlineWorkflow,
    GenerateReportWorkflow,
    GenerateWorldlineWorkflow,
    IngestCaseWorkflow,
    RunCouncilWorkflow,
)

TASK_QUEUE = "worldline-p0"


async def run_worker() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    client = await Client.connect(settings.temporal_address)
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[
            IngestCaseWorkflow,
            BuildMainlineWorkflow,
            GenerateWorldlineWorkflow,
            RunCouncilWorkflow,
            GenerateReportWorkflow,
        ],
    )
    logging.getLogger(__name__).info("Starting Temporal worker on %s queue=%s", settings.temporal_address, TASK_QUEUE)
    await worker.run()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
