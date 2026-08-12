#!/usr/bin/env bash

# 다음 날 기준의 로그 디렉터리와 00h~23h 시간대 디렉터리를 생성한다
.
set -euo pipefail

LOG_ROOT="/home/ec2-user/logs"
TARGET_DATE="$(date -d 'tomorrow' '+%y-%m-%d')"
HOURS=({00..23})

LOG_TYPES=(request sql health-check system_stat)

for crawler in faq car; do
  for log_type in "${LOG_TYPES[@]}"; do
    for hour in "${HOURS[@]}"; do
      mkdir -p "${LOG_ROOT}/${crawler}/${log_type}/${TARGET_DATE}/${hour}h"
    done
  done
done

for database in mongodb mysql; do
  for hour in "${HOURS[@]}"; do
    mkdir -p "${LOG_ROOT}/${database}/system_stat/${TARGET_DATE}/${hour}h"
  done
done

printf 'Created log directories for %s.\n' "${TARGET_DATE}"
