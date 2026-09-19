"""날짜/월 검증, 원자적 파일 쓰기, id 생성 등 공용 헬퍼 함수."""
import os
import re
import tempfile
from datetime import datetime
from typing import Iterable

from .exceptions import ValidationError

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")


def validate_date(date_str: str) -> None:
    """YYYY-MM-DD 형식과 실제 달력상 유효한 날짜인지 검증한다."""
    if not date_str or not DATE_PATTERN.match(date_str):
        raise ValidationError(
            f"날짜 형식이 올바르지 않습니다: {date_str}",
            hint="예: 2024-01-15 (YYYY-MM-DD)",
        )
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValidationError(
            f"날짜 형식이 올바르지 않습니다: {date_str}",
            hint="예: 2024-01-15 (YYYY-MM-DD)",
        )


def validate_month(month_str: str) -> None:
    """YYYY-MM 형식인지 검증한다."""
    if not month_str or not MONTH_PATTERN.match(month_str):
        raise ValidationError(
            f"월 형식이 올바르지 않습니다: {month_str}",
            hint="예: 2024-01 (YYYY-MM)",
        )


def atomic_write_lines(path: str, lines: Iterable[str]) -> None:
    """임시 파일에 먼저 쓴 뒤 os.replace로 원자적으로 교체한다.

    update/delete처럼 파일 전체를 다시 쓰는 상황에서, 쓰는 도중 프로그램이
    죽더라도 원본 파일이 손상되지 않도록(안정성/복구 가능성) 하기 위함이다.
    """
    dir_name = os.path.dirname(path) or "."
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, prefix=".tmp_", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            for line in lines:
                f.write(line)
                if not line.endswith("\n"):
                    f.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def next_transaction_id(existing_ids: Iterable[str]) -> str:
    """기존 id들 중 가장 큰 번호 + 1을 'TX-000001' 형식으로 반환한다."""
    max_num = 0
    for tid in existing_ids:
        try:
            num = int(tid.split("-")[-1])
            max_num = max(max_num, num)
        except (ValueError, IndexError):
            continue
    return f"TX-{max_num + 1:06d}"