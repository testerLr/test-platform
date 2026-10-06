import logging
import time
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline import (
    Pipeline, PipelineRun, PipelineRunStep, PipelineStep, RunStatus, StepRunStatus,
)
from app.pipeline_engine.errors import NodeExecutionError
from app.pipeline_engine.renderer import decrypt_credentials, render_step_template
from app.schemas.pipeline import pick_node_config

log = logging.getLogger("app.pipeline_engine")


class PipelineExecutor:
    def __init__(self, db: AsyncSession, run: PipelineRun, pipeline: Pipeline,
                 steps: list[PipelineStep], executor_registry: dict | None = None):
        self.db = db
        self.run = run
        self.pipeline = pipeline
        self.steps = sorted(steps, key=lambda s: s.order_index)
        self.context: dict = {"steps": []}
        self.executor_registry = executor_registry or {}

    def _resolve_executor(self, type_value: str):
        exe = self.executor_registry.get(type_value)
        if not exe:
            raise NodeExecutionError(f"no executor registered for type {type_value}", retryable=False)
        return exe

    async def _render_config(self, raw_config: dict) -> dict:
        def _walk(node):
            if isinstance(node, str):
                return render_step_template(node, self.context)
            if isinstance(node, dict):
                return {k: _walk(v) for k, v in node.items()}
            if isinstance(node, list):
                return [_walk(x) for x in node]
            return node
        return _walk(raw_config)

    async def _new_run_step(self, step: PipelineStep) -> PipelineRunStep:
        rs = PipelineRunStep(
            run_id=self.run.id,
            step_id=step.id,
            order_index=step.order_index,
            status=StepRunStatus.PENDING,
        )
        self.db.add(rs)
        await self.db.flush()
        return rs

    async def execute(self) -> dict:
        self.run.total_steps = len(self.steps)
        success_count = 0
        failure_count = 0
        skipped_count = 0
        processed_step_ids: set[int] = set()

        for step in self.steps:
            if not step.enabled:
                rs = await self._new_run_step(step)
                rs.status = StepRunStatus.SKIPPED
                rs.started_at = datetime.now(timezone.utc)
                rs.finished_at = datetime.now(timezone.utc)
                rs.duration_ms = 0
                skipped_count += 1
                processed_step_ids.add(step.id)
                self.context["steps"].append({"output": {}, "error": None, "skipped": True})
                continue

            rs = await self._new_run_step(step)
            processed_step_ids.add(step.id)
            rs.started_at = datetime.now(timezone.utc)
            t0 = time.perf_counter()
            try:
                pick_node_config(step.type.value, step.config)
                rendered = await self._render_config(step.config)
                rendered = decrypt_credentials(rendered)
                rs.input_rendered = rendered
                output = await self._resolve_executor(step.type.value).run(rendered)
                rs.output = output
                rs.status = StepRunStatus.SUCCESS
                self.context["steps"].append({"output": output})
                success_count += 1
                log.info("step success: id=%s type=%s duration_ms=%s", step.id, step.type.value, int((time.perf_counter() - t0) * 1000))
            except NodeExecutionError as e:
                rs.status = StepRunStatus.FAILED
                rs.error = str(e)
                self.context["steps"].append({"output": {}, "error": str(e)})
                failure_count += 1
                log.error("step failed: id=%s type=%s error=%s retryable=%s", step.id, step.type.value, e, e.retryable)
                break
            except Exception as e:
                rs.status = StepRunStatus.FAILED
                rs.error = f"unexpected: {e}"
                self.context["steps"].append({"output": {}, "error": str(e)})
                failure_count += 1
                log.exception("step unexpected error: id=%s", step.id)
                break
            finally:
                rs.finished_at = datetime.now(timezone.utc)
                rs.duration_ms = int((time.perf_counter() - t0) * 1000)
                await self.db.flush()

        if failure_count > 0:
            for remaining in self.steps:
                if remaining.id in processed_step_ids:
                    continue
                rs = await self._new_run_step(remaining)
                rs.status = StepRunStatus.SKIPPED
                rs.started_at = datetime.now(timezone.utc)
                rs.finished_at = datetime.now(timezone.utc)
                rs.duration_ms = 0
                skipped_count += 1
                processed_step_ids.add(remaining.id)
                self.context["steps"].append({"output": {}, "error": None, "skipped": True})

        self.run.success_count = success_count
        self.run.failure_count = failure_count
        self.run.skipped_count = skipped_count
        self.run.status = RunStatus.SUCCESS if failure_count == 0 else RunStatus.FAILED
        self.run.finished_at = datetime.now(timezone.utc)
        await self.db.commit()
        return {
            "run_id": self.run.id,
            "pipeline_id": self.pipeline.id,
            "status": self.run.status.value,
            "started_at": self.run.started_at.isoformat(),
            "finished_at": self.run.finished_at.isoformat(),
            "total_steps": self.run.total_steps,
            "success_count": success_count,
            "failure_count": failure_count,
            "skipped_count": skipped_count,
        }