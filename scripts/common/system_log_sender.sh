#!/usr/bin/env bash

set -euo pipefail

source "/home/ec2-user/conf/secret_envs.conf"
PEM_PATH="/home/ec2-user/MLO_01_001.pem"

SOURCE_DIR="/home/ec2-user/logs/system"
TARGET_DATE="$(date '+%y-%m-%d')"
TARGET_HOUR="$(date '+%Hh')"
REMOTE_DIR="/home/ec2-user/logs/mysql/system_stat/${TARGET_DATE}/${TARGET_HOUR}"

for number in {1..6}; do
  log_file="${SOURCE_DIR}/system_stat.log.${number}"

  scp -i "${PEM_PATH}" "${SOURCE_DIR}/system_stat.log.${number}" \
    "ec2-user@${DESTINATION_IP}:${REMOTE_DIR}/"
  rm -rf ${log_file}
done
