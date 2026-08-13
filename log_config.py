import logging
from pathlib import Path


# [포트폴리오 2.1] log_config.py - SQL 오류 로거 구성
# DB 연결 오류와 쿼리·데이터 오류를 서로 다른 파일에 기록할 수 있도록
# 두 개의 전용 로거를 생성하여 호출부에 반환하는 코드입니다.
def createLogger():
    # [포트폴리오 2.1] 로그 디렉터리 및 공통 출력 형식 설정
    # SQL 로그 디렉터리가 없으면 생성하고 모든 SQL 로그에 같은 형식을 적용합니다.
    log_dir = Path("/home/ec2-user/logs/sql")
    log_dir.mkdir(parents=True, exist_ok=True)

    log_format = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    # [포트폴리오 2.1] DB 연결 오류 전용 로거
    # MySQL 접속 실패나 연결 유실을 sql-connection-error.log에 기록합니다.
    connection_logger = logging.getLogger("sql_connection")
    connection_logger.setLevel(logging.ERROR)
    connection_logger.propagate = False

    # [포트폴리오 2.1] SQL·데이터 오류 전용 로거
    # 무결성·데이터 형식·기타 SQL 오류를 sql-query-error.log에 기록합니다.
    query_logger = logging.getLogger("sql_query")
    query_logger.setLevel(logging.ERROR)
    query_logger.propagate = False

    # [포트폴리오 2.1] 연결 오류 파일 핸들러 중복 생성 방지
    # 함수가 여러 번 호출되어도 같은 로그가 중복 출력되지 않게 합니다.
    if not connection_logger.handlers:
        connection_handler = logging.FileHandler(
            log_dir / "sql-connection-error.log",
            encoding="utf-8",
        )
        connection_handler.setFormatter(log_format)
        connection_logger.addHandler(connection_handler)

    # [포트폴리오 2.1] 쿼리 오류 파일 핸들러 중복 생성 방지
    if not query_logger.handlers:
        query_handler = logging.FileHandler(
            log_dir / "sql-query-error.log",
            encoding="utf-8",
        )
        query_handler.setFormatter(log_format)
        query_logger.addHandler(query_handler)

    return connection_logger, query_logger
