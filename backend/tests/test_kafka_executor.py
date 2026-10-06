import pytest

from app.pipeline_engine.errors import NodeExecutionError
from app.pipeline_engine.executors import kafka_executor as mod
from app.pipeline_engine.executors.kafka_executor import KafkaExecutor


class FakeMetadata:
    topic = "t"
    partition = 0
    offset = 7


class FakeProducer:
    def __init__(self, **kw):
        self.kw = kw

    async def start(self):
        pass

    async def send_and_wait(self, topic, key, value):
        return FakeMetadata()

    async def stop(self):
        pass


async def test_kafka_executor_success(monkeypatch):
    monkeypatch.setattr(mod, "AIOKafkaProducer", FakeProducer)
    exe = KafkaExecutor()
    out = await exe.run({
        "connection": {"bootstrap_servers": "h:9092"},
        "topic": "t",
        "key": "k",
        "value": '{"x":1}',
    })
    assert out == {"topic": "t", "partition": 0, "offset": 7}


async def test_kafka_executor_connection_error_retryable(monkeypatch):
    from aiokafka.errors import KafkaConnectionError

    class BrokenProducer(FakeProducer):
        async def start(self):
            raise KafkaConnectionError("can't connect")

    monkeypatch.setattr(mod, "AIOKafkaProducer", BrokenProducer)
    exe = KafkaExecutor()
    with pytest.raises(NodeExecutionError) as exc:
        await exe.run({
            "connection": {"bootstrap_servers": "h:9092"},
            "topic": "t",
            "value": "{}",
        })
    assert exc.value.retryable is True
