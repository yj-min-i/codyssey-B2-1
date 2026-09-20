"""서비스 계층 단위 테스트 (표준 라이브러리 unittest만 사용).

실행 방법(저장소 루트에서):
    python -m unittest discover -s tests -t .

각 테스트는 tempfile.TemporaryDirectory()로 만든 임시 폴더를 데이터 저장 위치로
사용하므로, 실제 ./data 를 건드리지 않고 매번 깨끗한 상태에서 검증한다.
"""
import os
import tempfile
import unittest

from budget_app.exceptions import NotFoundError, ValidationError
from budget_app.services import (
    BudgetService,
    CategoryService,
    RecurringService,
    SummaryService,
    TransactionService,
)
from budget_app.storage import (
    BudgetRepository,
    CategoryRepository,
    RecurringRepository,
    TransactionRepository,
)


class ServiceTestCase(unittest.TestCase):
    """공통 셋업: 임시 폴더에 저장소/서비스 4종을 새로 구성한다."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        data_dir = self.tmpdir.name

        self.cat_repo = CategoryRepository(os.path.join(data_dir, "categories.jsonl"))
        self.tx_repo = TransactionRepository(os.path.join(data_dir, "transactions.jsonl"))
        self.budget_repo = BudgetRepository(os.path.join(data_dir, "budgets.jsonl"))
        self.recurring_repo = RecurringRepository(os.path.join(data_dir, "recurring.jsonl"))

        self.category_service = CategoryService(self.cat_repo)
        self.category_service.ensure_default_categories()  # food/transport/rent/etc 생성

        self.tx_service = TransactionService(self.tx_repo, self.category_service)
        self.budget_service = BudgetService(self.budget_repo)
        self.summary_service = SummaryService(self.tx_service, self.budget_service)
        self.recurring_service = RecurringService(
            self.recurring_repo, self.category_service, self.tx_service
        )

    def tearDown(self):
        self.tmpdir.cleanup()


class TransactionServiceTests(ServiceTestCase):
    def test_add_creates_sequential_id_and_persists(self):
        tx1 = self.tx_service.add(
            type_="expense", date="2024-01-15", amount=15000, category="food", memo="점심"
        )
        tx2 = self.tx_service.add(
            type_="income", date="2024-01-14", amount=3000000, category="etc"
        )
        self.assertEqual(tx1.id, "TX-000001")
        self.assertEqual(tx2.id, "TX-000002")

        stored = list(self.tx_repo.iter_all())
        self.assertEqual(len(stored), 2)

    def test_add_rejects_invalid_date(self):
        with self.assertRaises(ValidationError):
            self.tx_service.add(
                type_="expense", date="2024-13-40", amount=1000, category="food"
            )

    def test_add_rejects_non_positive_amount(self):
        with self.assertRaises(ValidationError):
            self.tx_service.add(
                type_="expense", date="2024-01-01", amount=0, category="food"
            )
        with self.assertRaises(ValidationError):
            self.tx_service.add(
                type_="expense", date="2024-01-01", amount=-500, category="food"
            )

    def test_add_rejects_unknown_category(self):
        with self.assertRaises(ValidationError):
            self.tx_service.add(
                type_="expense", date="2024-01-01", amount=1000, category="없는카테고리"
            )

    def test_update_unknown_id_raises_not_found(self):
        with self.assertRaises(NotFoundError):
            self.tx_service.update("TX-999999", amount=1000)

    def test_delete_unknown_id_raises_not_found(self):
        with self.assertRaises(NotFoundError):
            self.tx_service.delete("TX-999999")

    def test_reassign_category_moves_matching_transactions_only(self):
        self.tx_service.add(type_="expense", date="2024-01-01", amount=1000, category="food")
        self.tx_service.add(type_="expense", date="2024-01-02", amount=2000, category="food")
        self.tx_service.add(type_="expense", date="2024-01-03", amount=3000, category="etc")

        moved = self.tx_service.reassign_category("food", "etc")

        self.assertEqual(moved, 2)
        categories_used = [tx.category for tx in self.tx_repo.iter_all()]
        self.assertNotIn("food", categories_used)
        self.assertEqual(categories_used.count("etc"), 3)


class CategoryServiceTests(ServiceTestCase):
    def test_ensure_default_categories_creates_four(self):
        names = self.category_service.list_names()
        self.assertEqual(set(names), {"food", "transport", "rent", "etc"})

    def test_add_rejects_duplicate(self):
        with self.assertRaises(ValidationError):
            self.category_service.add("food")

    def test_remove_blocked_when_category_in_use(self):
        self.tx_service.add(type_="expense", date="2024-01-01", amount=1000, category="food")
        with self.assertRaises(ValidationError):
            self.category_service.remove("food", self.tx_service.used_categories())

    def test_remove_succeeds_when_not_used(self):
        self.category_service.remove("rent", self.tx_service.used_categories())
        self.assertNotIn("rent", self.category_service.list_names())

    def test_remove_after_reassign_succeeds(self):
        """category remove --replace-with 가 내부적으로 쓰는 흐름을 그대로 재현."""
        self.tx_service.add(type_="expense", date="2024-01-01", amount=1000, category="food")
        self.tx_service.reassign_category("food", "etc")
        # 이관 후에는 더 이상 사용 중이 아니므로 삭제가 성공해야 한다.
        self.category_service.remove("food", self.tx_service.used_categories())
        self.assertNotIn("food", self.category_service.list_names())


class BudgetAndSummaryServiceTests(ServiceTestCase):
    def test_set_budget_upserts_same_month(self):
        self.budget_service.set_budget("2024-01", 300000)
        self.budget_service.set_budget("2024-01", 500000)  # 같은 달 재설정 -> 덮어쓰기

        budget = self.budget_service.get_budget("2024-01")
        self.assertEqual(budget.amount, 500000)
        self.assertEqual(len(list(self.budget_repo.iter_all())), 1)

    def test_set_budget_rejects_non_positive_amount(self):
        with self.assertRaises(ValidationError):
            self.budget_service.set_budget("2024-01", 0)

    def test_summary_reports_usage_rate_when_under_budget(self):
        self.budget_service.set_budget("2024-01", 100000)
        self.tx_service.add(type_="expense", date="2024-01-05", amount=40000, category="food")

        result = self.summary_service.monthly_summary("2024-01")

        self.assertTrue(result["has_data"])
        self.assertEqual(result["total_expense"], 40000)
        self.assertEqual(result["usage_rate"], 40.0)
        self.assertFalse(result["over_budget"])

    def test_summary_flags_over_budget_when_expense_exceeds_budget(self):
        self.budget_service.set_budget("2024-01", 10000)
        self.tx_service.add(type_="expense", date="2024-01-05", amount=15000, category="food")

        result = self.summary_service.monthly_summary("2024-01")

        self.assertEqual(result["usage_rate"], 150.0)
        self.assertTrue(result["over_budget"])

    def test_summary_top_categories_sorted_descending(self):
        self.tx_service.add(type_="expense", date="2024-01-01", amount=5000, category="food")
        self.tx_service.add(type_="expense", date="2024-01-02", amount=20000, category="rent")
        self.tx_service.add(type_="expense", date="2024-01-03", amount=10000, category="etc")

        result = self.summary_service.monthly_summary("2024-01", top=2)

        self.assertEqual(
            result["top_categories"], [("rent", 20000), ("etc", 10000)]
        )

    def test_summary_no_data_for_empty_month(self):
        result = self.summary_service.monthly_summary("2099-12")
        self.assertFalse(result["has_data"])


class RecurringServiceTests(ServiceTestCase):
    def test_add_rejects_invalid_day(self):
        with self.assertRaises(ValidationError):
            self.recurring_service.add(
                type_="expense", category="rent", amount=700000, day=29
            )

    def test_add_rejects_unknown_category(self):
        with self.assertRaises(ValidationError):
            self.recurring_service.add(
                type_="expense", category="없는카테고리", amount=1000, day=10
            )

    def test_apply_month_creates_transaction_for_each_rule(self):
        self.recurring_service.add(
            type_="income", category="etc", amount=3000000, day=25, memo="월급"
        )
        self.recurring_service.add(
            type_="expense", category="rent", amount=700000, day=5, memo="월세"
        )

        created = self.recurring_service.apply_month("2024-01")

        self.assertEqual(created, 2)
        txs = list(self.tx_repo.iter_all())
        self.assertEqual(len(txs), 2)
        dates = {tx.date for tx in txs}
        self.assertEqual(dates, {"2024-01-25", "2024-01-05"})

    def test_apply_month_is_idempotent_for_same_month(self):
        self.recurring_service.add(type_="expense", category="rent", amount=700000, day=5)

        first = self.recurring_service.apply_month("2024-01")
        second = self.recurring_service.apply_month("2024-01")  # 같은 달 재적용

        self.assertEqual(first, 1)
        self.assertEqual(second, 0)  # 중복 생성되지 않아야 한다
        self.assertEqual(len(list(self.tx_repo.iter_all())), 1)

    def test_apply_different_months_both_create_transactions(self):
        self.recurring_service.add(type_="expense", category="rent", amount=700000, day=5)

        self.recurring_service.apply_month("2024-01")
        self.recurring_service.apply_month("2024-02")

        self.assertEqual(len(list(self.tx_repo.iter_all())), 2)


if __name__ == "__main__":
    unittest.main()