"""Unix 时间戳转 UTC/北京时间"""
import sys
from datetime import datetime, timedelta, timezone

BJ = timezone(timedelta(hours=8))

if len(sys.argv) > 1:
    ts = int(sys.argv[1])
else:
    ts = int(input("输入 Unix 时间戳: "))

utc = datetime.fromtimestamp(ts, tz=timezone.utc)
bj = datetime.fromtimestamp(ts, tz=BJ)
now = datetime.now(BJ)

print(f"Unix:  {ts}")
print(f"UTC:   {utc.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"北京:  {bj.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"距今:  {(now - bj).total_seconds() / 60:.0f} 分钟前")
