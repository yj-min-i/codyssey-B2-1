"""앱 전용 예외 클래스 모음.

이 예외들은 사용자에게 보여줄 '원인 + 해결 힌트'를 담기 위한 것으로,
프로그램 내부 버그가 아니라 '예상 가능한 잘못된 입력/상태'를 표현한다.
"""


class AppError(Exception):
    """앱에서 의도적으로 발생시키는 오류의 기본 클래스.

    message: 사용자에게 보여줄 원인 설명
    hint: 사용자가 어떻게 고치면 되는지 알려주는 힌트(선택)
    """

    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.message = message
        self.hint = hint


class ValidationError(AppError):
    """입력값 검증에 실패했을 때 발생시키는 오류."""


class NotFoundError(AppError):
    """id/카테고리/월 등 조회 대상이 존재하지 않을 때 발생시키는 오류."""