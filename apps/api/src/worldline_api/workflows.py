from __future__ import annotations

from datetime import timedelta

from temporalio import workflow


@workflow.defn
class IngestCaseWorkflow:
    @workflow.run
    async def run(self, case_id: str) -> str:
        workflow.logger.info("Ingesting case %s", case_id)
        return f"ingested:{case_id}"


@workflow.defn
class BuildMainlineWorkflow:
    @workflow.run
    async def run(self, case_id: str) -> str:
        workflow.logger.info("Building mainline for %s", case_id)
        return f"mainline-ready:{case_id}"


@workflow.defn
class GenerateWorldlineWorkflow:
    @workflow.run
    async def run(self, mainline_id: str) -> str:
        workflow.logger.info("Generating worldline for %s", mainline_id)
        return f"worldline-ready:{mainline_id}"


@workflow.defn
class RunCouncilWorkflow:
    @workflow.run
    async def run(self, node_id: str) -> str:
        workflow.logger.info("Running council for %s", node_id)
        await workflow.sleep(timedelta(milliseconds=10))
        return f"council-ready:{node_id}"


@workflow.defn
class GenerateReportWorkflow:
    @workflow.run
    async def run(self, case_id: str) -> str:
        workflow.logger.info("Generating report for %s", case_id)
        return f"report-ready:{case_id}"

