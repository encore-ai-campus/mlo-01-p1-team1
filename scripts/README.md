# Log 및 파일 관리

## Log datalake

1. `make_directory.sh` : 로그 관리용 디렉토리 생성
    - File Path : `$/home/ec2-user/scripts/make_directory.sh`
    - 권한 : `100`
    - cron policy : `50 23 * * * bash /home/ec2-user/scripts/make_directory.sh`

## DB & Crawler 공통

- [x]  mysql : 10.0.5.119
- [x]  mongodb : 10.0.7.119
- [x]  car : 10.0.5.100
- [x]  faq : 10.0.7.34
1. cron 설치
    - `$sudo yum install cronie -y`
    - `$sudo systemctl start crond`
    - `$sudo systemctl enable crond`
    - `$sudo systemctl status crond`
2. `logrotate` 설치
    - `$sudo dnf install logrotate`
3. `system_stat_log_creator.sh` : 현재 Local PC의 stat을 파악하고 기록
    - File Path : `/home/ec2-user/scripts/system_stat_log_creator.sh`
    - cron policy : `*/1 * * * * bash /home/ec2-user/scripts/system_stat_log_creator.sh`
4. `system_stat.log`에 대해 logrotate 적용
    - logrotate policy : `rotate 6`, `missingok`
    - policy file path : `/home/ec2-user/conf/system_stat`
    - target file : `/home/ec2-user/logs/system/system_stat.log`
    - cron policy : `*/10 * * * * logrotate -f -s /home/ec2-user/conf/logrotate.status /home/ec2-user/conf/system_stat`
5. `system_log_sender.sh` : logrotate된 상태 로그를 log_datalake로 전송하는 후 삭제하는 스크립트
    - File Path : `/home/ec2-user/scripts/system_log_sender.sh`
    - cron policy : `* */1 * * * bash /home/ec2-user/scripts/system_log_sender.sh`
6. `conf/secret_envs.conf` 생성
    - `secret_envs.conf`파일에는 `DESTINATION_IP="10.0.7.165"`가 적힘
7. `/home/ec2-user/scripts/alert_system_stat.sh`
    - CPU 20%, Mem 20%, Disk 20% 각각이 이 기준을 넘으면 Discord로 Warning을 보내는 스크립트
    - cron policy : `*/10 * * * * bash /home/ec2-user/scripts/alert_system_stat.sh`

## Crawler Only

- [x]  car : 10.0.5.100
- [x]  faq : 10.0.7.34
1. `cron` 설치
    - `$sudo yum install cronie -y`
    - `$sudo systemctl start crond`
    - `$sudo systemctl enable crond`
    - `$sudo systemctl status crond`
2. `logrotate` 설치
    - `$sudo dnf install logrotate`
3. `/home/ec2-user/logs/request/non-exists-url-error.log`에 대해 logrotate 적용
    - logrotate policy : `rotate 6`, `missingok`
    - cron policy : `*/10 * * * * sudo logrotate -f /etc/logrotate.d/non-exist-url-error`
4. `/home/ec2-user/logs/sql/sql-connection-error.log`에 대해 logrotate 적용
    - logrotate policy : `rotate 6`, `missingok`
    - cron policy : `*/10 * * * * sudo logrotate -f /etc/logrotate.d/sql-connection-error`
5. `/home/ec2-user/logs/health-check/healthy.log`에 대해 logrotate 적용
    - logrotate policy : `rotate 6`, `missingok`
    - cron policy : `*/10 * * * * sudo logrotate -f /etc/logrotate.d/healthy`
6. `crawler_logs_sender.sh`
    - Target File
        1. `/home/ec2-user/logs/request/non-exists-url-error.log.{1..6}`
        2. `/home/ec2-user/logs/sql/sql-connection-error.log.{1..6}`
        3. `/home/ec2-user/logs/health-check/healthy.log.{1..6}`
    - 전송 `user@IP` : `ec2-user@${DESTINATION_IP}`
    - Destination Path
        - `/home/ec2-user/logs/car/request/YY-MM-DD/xxh/`
        - `/home/ec2-user/logs/car/sql/YY-MM-DD/xxh/`
        - `/home/ec2-user/logs/car/health-check/YY-MM-DD/xxh/`
    - cron policy : `* */1 * * * bash /home/ec2-user/scripts/crawler_logs_sender.sh`
