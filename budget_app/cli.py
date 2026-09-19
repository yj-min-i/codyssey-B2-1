"""CLI 계층: 명령행 인자를 파싱하고 서비스 계층을 호출한다."""
import argparse
import csv
import logging
import os
import sys

from .exceptions import AppError, ValidationError
from .decorators import track
from .models import Transaction
from .services import BudgetService, CategoryService, SummaryService, TransactionService
from .storage import BudgetRepository, CategoryRepository, TransactionRepository

DEFAULT_DATA_DIR = "./data"


def build_services(data_dir: str):
    os.makedirs(data_dir, exist_ok=True)
    tx_repo = TransactionRepository(os.path.join(data_dir, "transactions.jsonl"))
    cat_repo = CategoryRepository(os.path.join(data_dir, "categories.jsonl"))
    budget_repo = BudgetRepository(os.path.join(data_dir, "budgets.jsonl"))

    category_service = CategoryService(cat_repo)
    category_service.ensure_default_categories()
    tx_service = TransactionService(tx_repo, category_service)
    budget_service = BudgetService(budget_repo)
    summary_service = SummaryService(tx_service, budget_service)
    return tx_service, category_service, budget_service, summary_service


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="budget_app", description="나만의 용돈 기입장 콘솔 프로그램"
    )
    parser.add_argument(
        "--data-dir", default=DEFAULT_DATA_DIR, help="데이터 저장 폴더 (기본값: ./data)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("add", help="거래 추가 (대화형 입력)")

    p_list = sub.add_parser("list", help="거래 목록 조회 (최신순)")
    p_list.add_argument("--limit", type=int, default=10, help="출력할 최대 개수 (기본값: 10)")

    p_search = sub.add_parser("search", help="조건으로 거래 검색")
    p_search.add_argument("--from", dest="date_from", help="시작일 YYYY-MM-DD")
    p_search.add_argument("--to", dest="date_to", help="종료일 YYYY-MM-DD")
    p_search.add_argument("--category", help="카테고리")
    p_search.add_argument("--type", choices=["income", "expense"], help="타입")
    p_search.add_argument("--q", help="메모 키워드")
    p_search.add_argument("--tag", help="태그")

    p_summary = sub.add_parser("summary", help="월별 요약(총수입/총지출/잔액/카테고리 TOP N)")
    p_summary.add_argument("--month", required=True, help="YYYY-MM")
    p_summary.add_argument("--top", type=int, default=3, help="지출 TOP N (기본값: 3)")

    p_budget = sub.add_parser("budget", help="예산 설정")
    budget_sub = p_budget.add_subparsers(dest="budget_command", required=True)
    p_budget_set = budget_sub.add_parser("set", help="월 예산 설정")
    p_budget_set.add_argument("--month", required=True, help="YYYY-MM")
    p_budget_set.add_argument("--amount", required=True, type=int, help="예산 금액")

    p_category = sub.add_parser("category", help="카테고리 관리")
    category_sub = p_category.add_subparsers(dest="category_command", required=True)
    category_sub.add_parser("add", help="카테고리 추가 (대화형 입력)")
    category_sub.add_parser("list", help="카테고리 목록 조회")
    p_category_remove = category_sub.add_parser("remove", help="카테고리 삭제")
    p_category_remove.add_argument("--name", required=True, help="삭제할 카테고리 이름")

    p_update = sub.add_parser(
        "update", help="거래 수정 (--id 기반, 옵션으로 필드 지정)"
    )
    p_update.add_argument("--id", required=True, dest="tid")
    p_update.add_argument("--date")
    p_update.add_argument("--type", choices=["income", "expense"])
    p_update.add_argument("--category")
    p_update.add_argument("--amount", type=int)
    p_update.add_argument("--memo")
    p_update.add_argument("--tags", help="쉼표로 구분")

    p_delete = sub.add_parser("delete", help="거래 삭제")
    p_delete.add_argument("--id", required=True, dest="tid")

    p_import = sub.add_parser("import", help="CSV 파일로 거래 일괄 등록")
    p_import.add_argument("--from", required=True, dest="csv_path")

    p_export = sub.add_parser("export", help="조건에 맞는 거래를 CSV로 저장")
    p_export.add_argument("--out", required=True, dest="csv_path")
    p_export.add_argument("--month", help="YYYY-MM")
    p_export.add_argument("--from", dest="date_from", help="YYYY-MM-DD")
    p_export.add_argument("--to", dest="date_to", help="YYYY-MM-DD")

    return parser


def format_transaction(tx: Transaction) -> str:
    parts = [tx.id, tx.date, tx.type, tx.category, str(tx.amount), tx.memo or ""]
    if tx.tags:
        parts.append(",".join(tx.tags))
    return " | ".join(parts)


@track
def cmd_add(args, services):
    tx_service, *_ = services
    date = input("날짜(YYYY-MM-DD): ").strip()
    type_ = input("타입(income/expense): ").strip()
    category = input("카테고리: ").strip()
    amount = input("금액(양수): ").strip()
    memo = input("메모(선택): ").strip()
    tags_raw = input("태그(쉼표로 구분, 없으면 엔터): ").strip()
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []
    tx = tx_service.add(
        type_=type_, date=date, amount=amount, category=category, memo=memo, tags=tags
    )
    print(f"[저장 완료] id={tx.id}")


@track
def cmd_list(args, services):
    tx_service, *_ = services
    txs = tx_service.list_recent(limit=args.limit)
    if not txs:
        print("데이터 없음")
        return
    for tx in txs:
        print(format_transaction(tx))


@track
def cmd_search(args, services):
    tx_service, *_ = services
    txs = tx_service.search(
        date_from=args.date_from,
        date_to=args.date_to,
        category=args.category,
        type_=args.type,
        q=args.q,
        tag=args.tag,
    )
    if not txs:
        print("데이터 없음")
        return
    for tx in txs:
        print(format_transaction(tx))


@track
def cmd_summary(args, services):
    _, _, _, summary_service = services
    result = summary_service.monthly_summary(args.month, top=args.top)
    if not result["has_data"]:
        print("데이터 없음")
        return
    print(f"총 수입: {result['total_income']}원")
    print(f"총 지출: {result['total_expense']}원")
    print(f"잔액: {result['balance']}원")
    if result["budget"]:
        print(f"예산: {result['budget'].amount}원 (사용률 {result['usage_rate']}%)")
        if result["over_budget"]:
            print("[경고] 이번 달 예산을 초과했습니다!")
    print(f"\n지출 TOP {args.top}")
    if not result["top_categories"]:
        print("(지출 내역 없음)")
    for i, (cat, amt) in enumerate(result["top_categories"], start=1):
        print(f"{i}) {cat} {amt}원")


@track
def cmd_budget_set(args, services):
    _, _, budget_service, _ = services
    budget = budget_service.set_budget(args.month, args.amount)
    print(f"[저장 완료] {budget.month} 예산 {budget.amount}원")


@track
def cmd_category_add(args, services):
    _, category_service, *_ = services
    name = input("카테고리명: ").strip()
    category = category_service.add(name)
    print(f"[저장 완료] category={category.name}")


@track
def cmd_category_list(args, services):
    _, category_service, *_ = services
    names = category_service.list_names()
    if not names:
        print("데이터 없음")
        return
    for name in names:
        print(f"- {name}")


@track
def cmd_category_remove(args, services):
    tx_service, category_service, *_ = services
    category_service.remove(args.name, tx_service.used_categories())
    print(f"[삭제 완료] category={args.name}")


@track
def cmd_update(args, services):
    tx_service, *_ = services
    fields = {}
    if args.date is not None:
        fields["date"] = args.date
    if args.type is not None:
        fields["type"] = args.type
    if args.category is not None:
        fields["category"] = args.category
    if args.amount is not None:
        fields["amount"] = args.amount
    if args.memo is not None:
        fields["memo"] = args.memo
    if args.tags is not None:
        fields["tags"] = [t.strip() for t in args.tags.split(",") if t.strip()]
    tx = tx_service.update(args.tid, **fields)
    print(f"[수정 완료] id={tx.id}")


@track
def cmd_delete(args, services):
    tx_service, *_ = services
    tx_service.delete(args.tid)
    print(f"[삭제 완료] id={args.tid}")


@track
def cmd_import(args, services):
    tx_service, *_ = services
    if not os.path.exists(args.csv_path):
        raise ValidationError(f"파일을 찾을 수 없습니다: {args.csv_path}")

    imported = 0
    skipped = 0
    with open(args.csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                tags_raw = row.get("tags", "") or ""
                tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
                tx_service.add(
                    type_=(row.get("type") or "").strip(),
                    date=(row.get("date") or "").strip(),
                    amount=(row.get("amount") or "").strip(),
                    category=(row.get("category") or "").strip(),
                    memo=(row.get("memo") or "").strip(),
                    tags=tags,
                )
                imported += 1
            except (AppError, KeyError):
                skipped += 1
    print(f"[완료] imported={imported}, skipped={skipped}")


COMMAND_HANDLERS = {
    "add": cmd_add,
    "list": cmd_list,
    "search": cmd_search,
    "summary": cmd_summary,
    "update": cmd_update,
    "delete": cmd_delete,
    "import": cmd_import,
}


def main() -> int:
    logging.basicConfig(
        filename="app.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    parser = build_parser()
    args = parser.parse_args()

    try:
        services = build_services(args.data_dir)
    except AppError as e:
        print(f"[오류] {e.message}", file=sys.stderr)
        if e.hint:
            print(f"[힌트] {e.hint}", file=sys.stderr)
        return 1

    if args.command == "budget" and args.budget_command == "set":
        return cmd_budget_set(args, services)

    if args.command == "category":
        if args.category_command == "add":
            return cmd_category_add(args, services)
        if args.category_command == "list":
            return cmd_category_list(args, services)
        if args.category_command == "remove":
            return cmd_category_remove(args, services)

    if args.command in COMMAND_HANDLERS:
        return COMMAND_HANDLERS[args.command](args, services)

    parser.print_help()
    return 1