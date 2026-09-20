"""데이터 모델 정의.

dataclass로 거래(Transaction), 카테고리(Category), 예산(Budget)을 표현한다.
각 모델은 JSONL 저장을 위한 to_dict / from_dict를 함께 제공한다.
"""
from dataclasses import dataclass, field, asdict
from typing import List


@dataclass
class Transaction:
    """거래 1건을 표현하는 모델."""

    id: str
    type: str  # "income" 또는 "expense"
    date: str  # YYYY-MM-DD
    amount: int  # 항상 양수
    category: str
    memo: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Transaction":
        return cls(
            id=data["id"],
            type=data["type"],
            date=data["date"],
            amount=int(data["amount"]),
            category=data["category"],
            memo=data.get("memo", ""),
            tags=list(data.get("tags", [])),
        )


@dataclass
class Category:
    """카테고리 1건을 표현하는 모델."""

    name: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Category":
        return cls(name=data["name"])


@dataclass
class Budget:
    """특정 월의 예산 1건을 표현하는 모델."""

    month: str  # YYYY-MM
    amount: int

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Budget":
        return cls(month=data["month"], amount=int(data["amount"]))

@dataclass
class RecurringRule:
    """월급/월세처럼 매달 반복되는 거래를 만들어내는 규칙 1건."""

    type: str  # "income" 또는 "expense"
    category: str
    amount: int
    day: int  # 매달 며칠에 생성할지 (1~28)
    memo: str = ""
    tags: List[str] = field(default_factory=list)
    # apply(월)를 실행할 때마다 이 규칙으로 이미 거래를 생성한 월(YYYY-MM)을 기록해
    # 같은 월에 중복 생성되지 않도록 막는다.
    applied_months: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "RecurringRule":
        return cls(
            type=data["type"],
            category=data["category"],
            amount=int(data["amount"]),
            day=int(data["day"]),
            memo=data.get("memo", ""),
            tags=list(data.get("tags", [])),
            applied_months=list(data.get("applied_months", [])),
        )