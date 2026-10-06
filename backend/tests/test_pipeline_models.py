from app.models.pipeline import Pipeline, PipelineStep, PipelineRun, PipelineRunStep, StepType


def test_pipeline_step_type_enum():
    assert StepType.MYSQL.value == "mysql"
    assert StepType.KAFKA.value == "kafka"
    assert StepType.REDIS.value == "redis"
    assert StepType.HTTP.value == "http"


def test_orm_classes_register_on_metadata():
    tables = {"pipelines", "pipeline_steps", "pipeline_runs", "pipeline_run_steps"}
    from app.db.base import Base
    registered = set(Base.metadata.tables.keys())
    assert tables.issubset(registered)
