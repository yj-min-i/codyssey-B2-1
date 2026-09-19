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