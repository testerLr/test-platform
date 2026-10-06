from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError, KafkaTimeoutError

from app.pipeline_engine.errors import NodeExecutionError


class KafkaExecutor:
    type = "kafka"

    async def run(self, rendered_config: dict) -> dict:
        conn = rendered_config["connection"]
        producer = AIOKafkaProducer(
            bootstrap_servers=conn["bootstrap_servers"],
            security_protocol=conn.get("security_protocol", "PLAINTEXT"),
            sasl_plain_username=conn.get("sasl_username"),
            sasl_plain_password=conn.get("sasl_password"),
        )
        try:
            await producer.start()
            key_str = rendered_config.get("key")
            metadata = await producer.send_and_wait(
                topic=rendered_config["topic"],
                key=key_str.encode("utf-8") if key_str else None,
                value=rendered_config["value"].encode("utf-8"),
            )
            return {
                "topic": metadata.topic,
                "partition": metadata.partition,
                "offset": metadata.offset,
            }
        except (KafkaConnectionError, KafkaTimeoutError) as e:
            raise NodeExecutionError(f"kafka error: {e}", retryable=True) from e
        finally:
            await producer.stop()
