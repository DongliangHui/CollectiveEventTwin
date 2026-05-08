from __future__ import annotations

from uuid import uuid4

from temporalio.client import Client

from .config import settings
from .workflows import (
    BuildMainlineWorkflow,
    GenerateReportWorkflow,
    GenerateWorldlineWorkflow,
    IngestCaseWorkflow,
    RunCouncilWorkflow,
)

TASK_QUEUE = "worldline-p0"


async def execute_p0_workflow(workflow_name: str, *, case_id: str, target_id: str | None = None) -> tuple[str, str]:
    client = await Client.connect(settings.temporal_address)
    workflow_id = f"{workflow_name}-{target_id or case_id}-{uuid4().hex[:8]}"

    if workflow_name == "IngestCaseWorkflow":
        result = await client.execute_workflow(IngestCaseWorkflow.run, case_id, id=workflow_id, task_queue=TASK_QUEUE)
    elif workflow_name == "BuildMainlineWorkflow":
        result = await client.execute_workflow(BuildMainlineWorkflow.run, case_id, id=workflow_id, task_queue=TASK_QUEUE)
    elif workflow_name == "GenerateWorldlineWorkflow":
        result = await client.execute_workflow(GenerateWorldlineWorkflow.run, target_id or case_id, id=workflow_id, task_queue=TASK_QUEUE)
    elif workflow_name == "RunCouncilWorkflow":
        result = await client.execute_workflow(RunCouncilWorkflow.run, target_id or case_id, id=workflow_id, task_queue=TASK_QUEUE)
    elif workflow_name == "GenerateReportWorkflow":
        result = await client.execute_workflow(GenerateReportWorkflow.run, case_id, id=workflow_id, task_queue=TASK_QUEUE)
    else:
        raise ValueError(f"Unsupported workflow {workflow_name}")

    return workflow_id, result
