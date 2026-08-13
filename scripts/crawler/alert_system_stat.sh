#!/usr/bin/env bash

set -euo pipefail

source "/home/ec2-user/conf/secret_envs.conf"
LOG_FILE="/home/ec2-user/logs/system/system_stat.log"
THRESHOLD=20

[[ -f "${LOG_FILE}" ]] || {
  echo "Log file not found: ${LOG_FILE}" >&2
  exit 1
}

last_stats="$(tail -n 3 "${LOG_FILE}")"

# Amazon Linux awk 호환성을 위해 괄호를 정규식으로 처리하지 않고,
# 각 사용량 줄의 마지막 필드(예: 72.32%)에서 퍼센트 기호만 제거한다.
cpu_usage="$(awk '/CPU usage:/ { value = $NF; sub(/%$/, "", value); print value; exit }' <<< "${last_stats}")"
memory_usage="$(awk '/Memory usage:/ { value = $NF; sub(/%$/, "", value); print value; exit }' <<< "${last_stats}")"
disk_usage="$(awk '/Disk usage/ { value = $NF; sub(/%$/, "", value); print value; exit }' <<< "${last_stats}")"

[[ -n "${cpu_usage}" && -n "${memory_usage}" && -n "${disk_usage}" ]] || {
  echo "Could not parse the last three system-stat log lines." >&2
  exit 1
}

if awk -v cpu="${cpu_usage}" -v memory="${memory_usage}" -v disk="${disk_usage}" \
  -v threshold="${THRESHOLD}" 'BEGIN { exit !(cpu >= threshold || memory >= threshold || disk >= threshold) }'; then
  problems=()
  awk -v value="${cpu_usage}" -v threshold="${THRESHOLD}" 'BEGIN { exit !(value >= threshold) }' && problems+=("CPU ${cpu_usage}%")
  awk -v value="${memory_usage}" -v threshold="${THRESHOLD}" 'BEGIN { exit !(value >= threshold) }' && problems+=("Memory ${memory_usage}%")
  awk -v value="${disk_usage}" -v threshold="${THRESHOLD}" 'BEGIN { exit !(value >= threshold) }' && problems+=("Disk ${disk_usage}%")

  message="Car crawler : System resource warning: ${problems[*]} exceeded the ${THRESHOLD}% threshold. Current usage - CPU ${cpu_usage}%, Memory ${memory_usage}%, Disk ${disk_usage}%."

  curl --fail --silent --show-error \
    --header 'Content-Type: application/json' \
    --data "$(printf '{\"content\":\"%s\"}' "${message}")" \
    "${WEBHOOK_URL}"
fi
