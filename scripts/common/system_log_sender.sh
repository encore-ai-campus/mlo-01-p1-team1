#!/usr/bin/env bash

set -euo pipefail

source "/home/ec2-user/conf/secret_envs.conf"
PEM_PATH="/home/ec2-user/MLO_01_001.pem"

SOURCE_DIR="/home/ec2-user/logs/system"
TARGET_DATE="$(date '+%y-%m-%d')"
TARGET_HOUR="$(date '+%Hh')"
REMOTE_DIR="/home/ec2-user/logs/faq/system_state/${TARGET_DATE}/${TARGET_HOUR}"

scp -i ${PEM_PATH} "${SOURCE_DIR}"/system_stat.log.{1..6} "ec2-user@${DESTINATION_IP}:${REMOTE_DIR}/"
