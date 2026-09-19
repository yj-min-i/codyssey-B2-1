"""저장소(Repository) 계층.

파일 입출력을 담당한다. 조회는 제너레이터(yield)로 한 줄씩 읽어
파일 전체를 메모리에 올리지 않는다. update/delete처럼 전체를 다시 써야 할
때는 atomic_write_lines로 임시 파일 → 원자적 교체(rename) 방식을 쓴다.
"""
import json
import os
from typing import Iterator, List, Optional

from .models import Budget, Category, Transaction
from .utils import atomic_write_lines, next_transaction_id


def _ensure_file(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        open(path, "w", encoding="utf-8").close()


class TransactionRepository:
    def __init__(self, path: str):
        self.path = path

    def iter_all(self) -> Iterator[Transaction]:
        """파일을 한 줄씩(제너레이터로) 읽어 Transaction 객체를 생성한다."""
        _ensure_file(self.path)
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                yield Transaction.from_dict(data)

    def append(self, transaction: Transaction) -> None:
        _ensure_file(self.path)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(transaction.to_dict(), ensure_ascii=False) + "\n")

    def rewrite_all(self, transactions: List[Transaction]) -> None:
        lines = (json.dumps(t.to_dict(), ensure_ascii=False) for t in transactions)
        atomic_write_lines(self.path, lines)

    def next_id(self) -> str:
        return next_transaction_id(t.id for t in self.iter_all())


class CategoryRepository:
    def __init__(self, path: str):
        self.path = path

    def iter_all(self) -> Iterator[Category]:
        _ensure_file(self.path)
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                yield Category.from_dict(data)

    def append(self, category: Category) -> None:
        _ensure_file(self.path)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(category.to_dict(), ensure_ascii=False) + "\n")

    def rewrite_all(self, categories: List[Category]) -> None:
        lines = (json.dumps(c.to_dict(), ensure_ascii=False) for c in categories)
        atomic_write_lines(self.path, lines)


class BudgetRepository:
    def __init__(self, path: str):
        self.path = path

    def iter_all(self) -> Iterator[Budget]:
        _ensure_file(self.path)
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                yield Budget.from_dict(data)

    def upsert(self, budget: Budget) -> None:
        """같은 월(month)의 기존 예산이 있으면 교체, 없으면 추가한다."""
        budgets = [b for b in self.iter_all() if b.month != budget.month]
        budgets.append(budget)
        lines = (json.dumps(b.to_dict(), ensure_ascii=False) for b in budgets)
        atomic_write_lines(self.path, lines)

    def get(self, month: str) -> Optional[Budget]:
        for b in self.iter_all():
            if b.month == month:
                return b
        return None