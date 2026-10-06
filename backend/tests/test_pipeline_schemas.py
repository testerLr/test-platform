import pytest
from pydantic import ValidationError

from app.schemas.pipeline import (
    HttpConfig, KafkaConfig, MySQLConfig, RedisConfig, StepCreate, pick_node_config,
)


def test_mysql_config_ok():
    c = MySQLConfig.model_validate({
        "connection": {"host": "h", "port": 3306, "user": "u", "password": "p", "database": "d"},
        "sql": "INSERT INTO x VALUES (%s)",
        "params": {"v": 1},
    })
    assert c.connection.host == "h"


def test_kafka_config_ok():
    c = KafkaConfig.model_validate({
        "connection": {"bootstrap_servers": "h:9092"},
        "topic": "t",
        "value": '{"x":1}',
    })
    assert c.topic == "t"


def test_redis_config_rejects_non_set_operation():
    with pytest.raises(ValidationError):
        RedisConfig.model_validate({
            "connection": {"host": "h"},
            "operation": "hset",
            "key": "k",
            "value": "v",
        })


def test_http_config_ok():
    c = HttpConfig.model_validate({
        "method": "POST",
        "url": "http://x/y",
        "body": '{"a":1}',
    })
    assert c.timeout_seconds == 30  # default


def test_pick_node_config_dispatches_by_type():
    raw = {"connection": {"host": "h", "port": 3306, "user": "u", "password": "p", "database": "d"}, "sql": "SELECT 1"}
    cfg = pick_node_config("mysql", raw)
    assert isinstance(cfg, MySQLConfig)


def test_step_create_rejects_config_type_mismatch():
    with pytest.raises(ValidationError):
        StepCreate.model_validate({
            "type": "mysql",
            "name": "x",
            "config": {"connection": {"host": "h"}, "topic": "t", "value": "{}"},  # kafka-shaped for mysql type
        })
