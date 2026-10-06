import asyncmy

from app.pipeline_engine.errors import NodeExecutionError


class MySQLExecutor:
    type = "mysql"

    async def run(self, rendered_config: dict) -> dict:
        conn_cfg = rendered_config["connection"]
        sql = rendered_config["sql"]
        params = rendered_config.get("params", {})

        conn = None
        try:
            conn = await asyncmy.connect(
                host=conn_cfg["host"],
                port=conn_cfg["port"],
                user=conn_cfg["user"],
                password=conn_cfg["password"],
                db=conn_cfg["database"],
                autocommit=True,
            )
            async with conn.cursor() as cur:
                if params:
                    keys = list(params.keys())
                    values = tuple(params[k] for k in keys)
                    sql_params = _named_to_positional(sql, keys)
                    await cur.execute(sql_params, values)
                else:
                    await cur.execute(sql)
                affected = cur.rowcount
                inserted_id = cur.lastrowid
            return {"affected_rows": affected, "inserted_id": inserted_id}
        except asyncmy.errors.OperationalError as e:
            raise NodeExecutionError(f"mysql connection error: {e}", retryable=True) from e
        except asyncmy.errors.ProgrammingError as e:
            raise NodeExecutionError(f"mysql sql error: {e}", retryable=False, details={"sql": sql}) from e
        except asyncmy.errors.IntegrityError as e:
            raise NodeExecutionError(f"mysql integrity error: {e}", retryable=False) from e
        finally:
            if conn is not None:
                await conn.ensure_closed()


def _named_to_positional(sql: str, keys: list[str]) -> str:
    """Replace %(name)s placeholders with %s in given key order."""
    out = sql
    for k in keys:
        out = out.replace(f"%({k})s", "%s")
    return out