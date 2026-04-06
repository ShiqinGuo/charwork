from snowflake import SnowflakeGenerator


generator = SnowflakeGenerator(42)


def generate_id() -> str:
    """
    功能描述：
        生成标识。

    参数：
        无。

    返回值：
        str: 返回str类型的处理结果。
    """
    return str(next(generator))
