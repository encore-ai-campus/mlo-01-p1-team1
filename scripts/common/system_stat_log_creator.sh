#!/usr/bin/env bash

set -euo pipefail

LOG_FILE="/home/ec2-user/logs/system/system_stat.log"
DISK_PATH="/"

mkdir -p "$(dirname "${LOG_FILE}")"

read_cpu() {
  awk '/^cpu / { idle = $5 + $6; total = 0; for (i = 2; i <= NF; i++) total += $i; print total, idle; exit }' /proc/stat
}

read -r total_before idle_before < <(read_cpu)
sleep 1
read -r total_after idle_after < <(read_cpu)

cpu_usage="$(awk -v total_before="${total_before}" -v idle_before="${idle_before}" \
  -v total_after="${total_after}" -v idle_after="${idle_after}" '
  BEGIN {
    total_delta = total_after - total_before
    idle_delta = idle_after - idle_before
    if (total_delta == 0) print "0.00"
    else printf "%.2f", (total_delta - idle_delta) * 100 / total_delta
  }')"

mem_usage="$(awk '
  /^MemTotal:/ { total = $2 }
  /^MemAvailable:/ { available = $2 }
  END {
    if (total == 0) print "0.00"
    else printf "%.2f", (total - available) * 100 / total
  }' /proc/meminfo)"

disk_usage="$(df -P "${DISK_PATH}" | awk 'NR == 2 { gsub(/%/, "", $5); print $5 }')"
timestamp="$(date '+%Y-%m-%d %H:%M:%S %Z')"

{
  printf '[%s] CPU usage: %s%%\n' "${timestamp}" "${cpu_usage}"
  printf '[%s] Memory usage: %s%%\n' "${timestamp}" "${mem_usage}"
  printf '[%s] Disk usage (%s): %s%%\n' "${timestamp}" "${DISK_PATH}" "${disk_usage}"
} >> "${LOG_FILE}"

