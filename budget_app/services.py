"""서비스 계층: 입력 검증 + 비즈니스 로직을 담당한다.

CLI 계층은 이 서비스들만 호출하고, 서비스는 저장소(storage.py)만 호출한다.
"""
from typing import List, Optional, Set, Union

from typing import List, Optional, Set, Union

from .exceptions import NotFoundError, ValidationError
from .models import Category, Transaction
from .storage import CategoryRepository, TransactionRepository
from .utils import validate_date, validate_month

VALID_TYPES = ("income", "expense")
DEFAULT_CATEGORIES = ("food", "transport", "rent", "etc")


class CategoryService:
    def __init__(self, repo: CategoryRepository):
        self.repo = repo

    def list_names(self) -> List[str]:
        return [c.name for c in self.repo.iter_all()]

    def exists(self, name: str) -> bool:
        return name in self.list_names()

    def ensure_default_categories(self) -> None:
        """카테고리 파일이 비어 있으면 기본 카테고리를 자동 생성한다."""
        if not self.list_names():
            for name in DEFAULT_CATEGORIES:
                self.repo.append(Category(name=name))

    def add(self, name: str) -> Category:
        name = (name or "").strip()
        if not name:
            raise ValidationError("카테고리 이름이 비어 있습니다.", hint="예: food")
        if self.exists(name):
            raise ValidationError(f"이미 존재하는 카테고리입니다: {name}")
        category = Category(name=name)
        self.repo.append(category)
        return category

    def remove(self, name: str, used_categories: Set[str]) -> None:
        if not self.exists(name):
            raise NotFoundError(f"존재하지 않는 카테고리입니다: {name}")
        if name in used_categories:
            raise ValidationError(
                f"'{name}' 카테고리를 사용 중인 거래가 있어 삭제할 수 없습니다.",
                hint="update로 해당 거래들을 다른 카테고리로 먼저 옮기세요.",
            )
        remaining = [c for c in self.repo.iter_all() if c.name != name]
        self.repo.rewrite_all(remaining)

class TransactionService:
    def __init__(self, repo: TransactionRepository, category_service: CategoryService):
        self.repo = repo
        self.category_service = category_service

    def _validate(self, type_: str, date: str, amount: Union[int, str], category: str) -> int:
        if type_ not in VALID_TYPES:
            raise ValidationError(
                f"허용되지 않은 타입입니다: {type_}",
                hint="income 또는 expense 중 하나를 입력하세요.",
            )
        validate_date(date)
        try:
            amount_int = int(amount)
        except (TypeError, ValueError):
            raise ValidationError(f"금액은 숫자여야 합니다: {amount}")
        if amount_int <= 0:
            raise ValidationError(
                f"금액은 0보다 큰 양수여야 합니다: {amount_int}", hint="예: 15000"
            )
        if not self.category_service.exists(category):
            raise ValidationError(
                f"등록되지 않은 카테고리입니다: {category}",
                hint="category add 로 먼저 등록하세요. 등록된 카테고리: "
                + ", ".join(self.category_service.list_names()),
            )
        return amount_int

    def add(
        self,
        type_: str,
        date: str,
        amount: Union[int, str],
        category: str,
        memo: str = "",
        tags: Optional[List[str]] = None,
    ) -> Transaction:
        amount_int = self._validate(type_, date, amount, category)
        tx = Transaction(
            id=self.repo.next_id(),
            type=type_,
            date=date,
            amount=amount_int,
            category=category,
            memo=memo,
            tags=tags or [],
        )
        self.repo.append(tx)
        return tx

    def list_recent(self, limit: int = 10) -> List[Transaction]:
        all_tx = sorted(self.repo.iter_all(), key=lambda t: (t.date, t.id), reverse=True)
        return all_tx[:limit]

    def search(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        category: Optional[str] = None,
        type_: Optional[str] = None,
        q: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[Transaction]:
        results = []
        for tx in self.repo.iter_all():
            if date_from and tx.date < date_from:
                continue
            if date_to and tx.date > date_to:
                continue
            if category and tx.category != category:
                continue
            if type_ and tx.type != type_:
                continue
            if q and q not in tx.memo:
                continue
            if tag and tag not in tx.tags:
                continue
            results.append(tx)
        results.sort(key=lambda t: (t.date, t.id), reverse=True)
        return results

    def update(self, tid: str, **fields) -> Transaction:
        all_tx = list(self.repo.iter_all())
        target = next((tx for tx in all_tx if tx.id == tid), None)
        if target is None:
            raise NotFoundError(f"존재하지 않는 거래 id입니다: {tid}")

        new_type = fields.get("type") if fields.get("type") is not None else target.type
        new_date = fields.get("date") if fields.get("date") is not None else target.date
        new_category = (
            fields.get("category") if fields.get("category") is not None else target.category
        )
        new_amount = fields.get("amount") if fields.get("amount") is not None else target.amount
        new_memo = fields.get("memo") if fields.get("memo") is not None else target.memo
        new_tags = fields.get("tags") if fields.get("tags") is not None else target.tags

        amount_int = self._validate(new_type, new_date, new_amount, new_category)

        target.type = new_type
        target.date = new_date
        target.category = new_category
        target.amount = amount_int
        target.memo = new_memo
        target.tags = new_tags

        self.repo.rewrite_all(all_tx)
        return target

    def delete(self, tid: str) -> None:
        all_tx = list(self.repo.iter_all())
        remaining = [tx for tx in all_tx if tx.id != tid]
        if len(remaining) == len(all_tx):
            raise NotFoundError(f"존재하지 않는 거래 id입니다: {tid}")
        self.repo.rewrite_all(remaining)

    def used_categories(self) -> Set[str]:
        return {tx.category for tx in self.repo.iter_all()}

    def reassign_category(self, old_category: str, new_category: str) -> int:
        """old_category를 쓰는 모든 거래를 new_category로 일괄 이관한다.

        카테고리를 삭제하기 전, 그 카테고리를 사용 중인 거래를 다른 카테고리로
        옮기기 위해 사용한다. 이관된 거래 건수를 반환한다.
        """
        all_tx = list(self.repo.iter_all())
        moved = 0
        for tx in all_tx:
            if tx.category == old_category:
                tx.category = new_category
                moved += 1
        if moved:
            self.repo.rewrite_all(all_tx)
        return moved

class BudgetService:
    def __init__(self, repo):
        self.repo = repo

    def set_budget(self, month: str, amount: Union[int, str]):
        validate_month(month)
        try:
            amount_int = int(amount)
        except (TypeError, ValueError):
            raise ValidationError(f"예산 금액은 숫자여야 합니다: {amount}")
        if amount_int <= 0:
            raise ValidationError("예산 금액은 0보다 커야 합니다.")
        from .models import Budget

        budget = Budget(month=month, amount=amount_int)
        self.repo.upsert(budget)
        return budget

    def get_budget(self, month: str):
        return self.repo.get(month)


class SummaryService:
    def __init__(self, tx_service: TransactionService, budget_service: BudgetService):
        self.tx_service = tx_service
        self.budget_service = budget_service

    def monthly_summary(self, month: str, top: int = 3) -> dict:
        validate_month(month)
        txs = [t for t in self.tx_service.repo.iter_all() if t.date.startswith(month)]

        total_income = sum(t.amount for t in txs if t.type == "income")
        total_expense = sum(t.amount for t in txs if t.type == "expense")
        balance = total_income - total_expense

        category_totals: dict = {}
        for t in txs:
            if t.type == "expense":
                category_totals[t.category] = category_totals.get(t.category, 0) + t.amount
        top_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:top]

        budget = self.budget_service.get_budget(month)
        usage_rate = None
        over_budget = False
        if budget and budget.amount:
            usage_rate = round(total_expense / budget.amount * 100, 1)
            over_budget = total_expense > budget.amount

        return {
            "has_data": bool(txs),
            "total_income": total_income,
            "total_expense": total_expense,
            "balance": balance,
            "top_categories": top_categories,
            "budget": budget,
            "usage_rate": usage_rate,
            "over_budget": over_budget,
        }