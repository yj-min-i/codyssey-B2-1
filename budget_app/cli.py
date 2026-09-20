"""CLI 계층: 명령행 인자를 파싱하고 서비스 계층을 호출한다."""
import argparse
import csv
import logging
import os
import shutil
import sys
from datetime import datetime
from typing import Tuple

from .decorators import logger, track
from .exceptions import AppError, ValidationError
from .models import Transaction
from .services import BudgetService, CategoryService, SummaryService, TransactionService
from .storage import BudgetRepository, CategoryRepository, TransactionRepository
from .utils import validate_date, validate_month

DEFAULT_DATA_DIR = "./data"

# CLI 계층에서 서비스 4종을 하나로 묶어 주고받는 타입. build_services()가 만들고
# 모든 cmd_* 핸들러가 이 튜플을 그대로 받아 필요한 서비스만 꺼내 쓴다.
Services = Tuple[TransactionService, CategoryService, BudgetService, SummaryService]


def build_services(data_dir: str) -> Services:
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
    p_category_remove.add_argument(
        "--replace-with",
        dest="replace_with",
        help="사용 중인 카테고리를 삭제할 때, 해당 거래들을 옮길 대체 카테고리",
    )

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

    sub.add_parser("backup", help="데이터 파일 3종을 타임스탬프 폴더에 백업")

    return parser


def format_transaction(tx: Transaction) -> str:
    parts = [tx.id, tx.date, tx.type, tx.category, str(tx.amount), tx.memo or ""]
    if tx.tags:
        parts.append(",".join(tx.tags))
    return " | ".join(parts)


@track
def cmd_add(args: argparse.Namespace, services: Services) -> None:
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
def cmd_list(args: argparse.Namespace, services: Services) -> None:
    tx_service, *_ = services
    txs = tx_service.list_recent(limit=args.limit)
    if not txs:
        print("데이터 없음")
        return
    for tx in txs:
        print(format_transaction(tx))


@track
def cmd_search(args: argparse.Namespace, services: Services) -> None:
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
def cmd_summary(args: argparse.Namespace, services: Services) -> None:
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
def cmd_budget_set(args: argparse.Namespace, services: Services) -> None:
    _, _, budget_service, _ = services
    budget = budget_service.set_budget(args.month, args.amount)
    print(f"[저장 완료] {budget.month} 예산 {budget.amount}원")


@track
def cmd_category_add(args: argparse.Namespace, services: Services) -> None:
    _, category_service, *_ = services
    name = input("카테고리명: ").strip()
    category = category_service.add(name)
    print(f"[저장 완료] category={category.name}")


@track
def cmd_category_list(args: argparse.Namespace, services: Services) -> None:
    _, category_service, *_ = services
    names = category_service.list_names()
    if not names:
        print("데이터 없음")
        return
    for name in names:
        print(f"- {name}")


@track
def cmd_category_remove(args: argparse.Namespace, services: Services) -> None:
    tx_service, category_service, *_ = services
    used = tx_service.used_categories()
    if args.name in used:
        if not args.replace_with:
            raise ValidationError(
                f"'{args.name}' 카테고리를 사용 중인 거래가 있어 삭제할 수 없습니다.",
                hint="update로 거래를 하나씩 옮기거나, --replace-with <대체카테고리>로 한 번에 옮기세요.",
            )
        if args.replace_with == args.name:
            raise ValidationError("대체 카테고리는 삭제할 카테고리와 달라야 합니다.")
        if not category_service.exists(args.replace_with):
            raise ValidationError(f"대체 카테고리가 존재하지 않습니다: {args.replace_with}")
        moved = tx_service.reassign_category(args.name, args.replace_with)
        print(f"[안내] {moved}건의 거래를 '{args.replace_with}' 카테고리로 이관했습니다.")
    category_service.remove(args.name, tx_service.used_categories())
    print(f"[삭제 완료] category={args.name}")


@track
def cmd_update(args: argparse.Namespace, services: Services) -> None:
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
def cmd_delete(args: argparse.Namespace, services: Services) -> None:
    tx_service, *_ = services
    tx_service.delete(args.tid)
    print(f"[삭제 완료] id={args.tid}")


@track
def cmd_import(args: argparse.Namespace, services: Services) -> None:
    tx_service, *_ = services
    if not os.path.exists(args.csv_path):
        raise ValidationError(f"파일을 찾을 수 없습니다: {args.csv_path}")

    imported = 0
    skipped = 0
    with open(args.csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        # row_num은 실제 CSV 파일 기준 줄 번호(1행=헤더)로, 로그에서 문제 행을 바로 찾게 해준다.
        for row_num, row in enumerate(reader, start=2):
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
            except AppError as e:
                skipped += 1
                logger.warning("[import 건너뜀] %s %d행: %s", args.csv_path, row_num, e.message)
            except KeyError as e:
                skipped += 1
                logger.warning(
                    "[import 건너뜀] %s %d행: 필수 컬럼 누락(%s)", args.csv_path, row_num, e
                )
    print(f"[완료] imported={imported}, skipped={skipped}")
    if skipped:
        print("[안내] 건너뛴 행의 상세 사유는 app.log에서 확인할 수 있습니다.")


@track
def cmd_export(args: argparse.Namespace, services: Services) -> None:
    tx_service, *_ = services
    if not args.month and not (args.date_from and args.date_to):
        raise ValidationError(
            "export는 --month 또는 --from/--to 조건이 필요합니다.",
            hint="예: export --out out.csv --month 2024-01",
        )

    if args.month:
        validate_month(args.month)
        date_from, date_to = f"{args.month}-01", f"{args.month}-31"
    else:
        validate_date(args.date_from)
        validate_date(args.date_to)
        date_from, date_to = args.date_from, args.date_to

    txs = tx_service.search(date_from=date_from, date_to=date_to)
    with open(args.csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "type", "category", "amount", "memo", "tags"])
        for tx in txs:
            writer.writerow(
                [tx.date, tx.type, tx.category, tx.amount, tx.memo, ",".join(tx.tags)]
            )
    print(f"[완료] {args.csv_path} ({len(txs)} records)")


@track
def cmd_backup(args: argparse.Namespace, services: Services) -> None:
    data_dir = args.data_dir
    if not os.path.isdir(data_dir):
        raise ValidationError(f"데이터 폴더가 없습니다: {data_dir}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(data_dir, "backup", timestamp)
    os.makedirs(backup_dir, exist_ok=True)

    copied = []
    for fname in ("transactions.jsonl", "categories.jsonl", "budgets.jsonl"):
        src = os.path.join(data_dir, fname)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(backup_dir, fname))
            copied.append(fname)

    print(f"[완료] 백업 생성: {backup_dir} ({len(copied)}개 파일)")


COMMAND_HANDLERS = {
    "add": cmd_add,
    "list": cmd_list,
    "search": cmd_search,
    "summary": cmd_summary,
    "update": cmd_update,
    "delete": cmd_delete,
    "import": cmd_import,
    "export": cmd_export,
    "backup": cmd_backup,
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