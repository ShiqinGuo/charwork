from snowflake import SnowflakeGenerator


generator = SnowflakeGenerator(42)


def generate_id() -> str:
    return str(next(generator))
