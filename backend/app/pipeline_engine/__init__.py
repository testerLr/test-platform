from app.pipeline_engine.executors.http_executor import HttpExecutor
from app.pipeline_engine.executors.kafka_executor import KafkaExecutor
from app.pipeline_engine.executors.mysql_executor import MySQLExecutor
from app.pipeline_engine.executors.redis_executor import RedisExecutor


def default_executor_registry() -> dict[str, object]:
    return {
        "mysql": MySQLExecutor(),
        "kafka": KafkaExecutor(),
        "redis": RedisExecutor(),
        "http": HttpExecutor(),
    }


__all__ = ["default_executor_registry"]