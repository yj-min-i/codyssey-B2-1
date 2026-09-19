"""공통 관심사를 분리하는 데코레이터 모음.

track 데코레이터는 CLI 명령 함수(cmd_*)에 적용되어
1) 실행 로그 기록, 2) 실행 시간 측정, 3) 예외를 스택트레이스 없이
'[오류] 원인' + '[힌트] 해결 방법' 형태로 출력하는 역할을 모두 담당한다.
반환값은 그대로 종료 코드(exit code)로 사용된다(성공 0 / 실패 1).
"""
import functools
import logging
import sys
import time

from .exceptions import AppError

logger = logging.getLogger("budget_app")


def track(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        logger.info("[시작] %s", func.__name__)
        try:
            func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            logger.info("[완료] %s (%.3f초)", func.__name__, elapsed)
            return 0
        except AppError as e:
            elapsed = time.perf_counter() - start
            logger.error("[오류] %s: %s (%.3f초)", func.__name__, e.message, elapsed)
            print(f"[오류] {e.message}", file=sys.stderr)
            if e.hint:
                print(f"[힌트] {e.hint}", file=sys.stderr)
            return 1
        except Exception as e:
            # 예상하지 못한 오류도 스택트레이스 대신 원인 + 힌트 형태로 출력한다.
            elapsed = time.perf_counter() - start
            logger.error("[예외] %s: %s (%.3f초)", func.__name__, e, elapsed)
            print(f"[오류] 예상치 못한 문제가 발생했습니다: {e}", file=sys.stderr)
            print("[힌트] 입력값을 다시 확인해 주세요.", file=sys.stderr)
            return 1

    return wrapper