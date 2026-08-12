#!/usr/bin/env bash

set -euo pipefail

source "/home/ec2-user/conf/secret_envs.conf"
PEM_PATH="/home/ec2-user/MLO_01_001.pem"
TARGET_DATE="$(date '+%y-%m-%d')"
TARGET_HOUR="$(date '+%Hh')"

send_logs() {
  local source_dir="$1"
  local log_name="$2"
  local destination_type="$3"
  local number
  local remote_dir="/home/ec2-user/logs/car/${destination_type}/${TARGET_DATE}/${TARGET_HOUR}"

  for number in {1..6}; do
    scp -i "${PEM_PATH}" "${source_dir}/${log_name}.${number}" \
      "ec2-user@${DESTINATION_IP}:${remote_dir}/"
  done
}

send_logs "/home/ec2-user/logs/request" "non-exists-url-error.log" "request"
send_logs "/home/ec2-user/logs/sql" "sql-connection-error.log" "sql"
send_logs "/home/ec2-user/logs/health-check" "healthy.log" "health-check"
