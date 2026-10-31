#!/usr/bin/env bash
# 反复运行一个取数任务，直到它正常结束（每页都存盘，重跑会跳过已取的页）
cd "$(dirname "$0")"
for i in $(seq 1 30); do
  I1_MIN_INTERVAL=4.2 ../../1_overreaction/.venv/bin/python fetch_indexone.py ../raw/indexone_20261030 "$@" && exit 0
  echo "第 $i 次中断，60 秒后重试"; sleep 60
done
exit 1
