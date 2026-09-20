# 나만의 용돈 기입장

Python 표준 라이브러리만으로 만든 파일 기반 콘솔 가계부입니다.
거래 추가/조회/검색/수정/삭제, 월별 요약, 카테고리·예산 관리, CSV 가져오기/내보내기, 데이터 백업을 지원합니다.

## 목차

- [실행 방법](#실행-방법)
- [프로젝트 구조](#프로젝트-구조)
- [아키텍처](#아키텍처)
- [모듈별 공개 API](#모듈별-공개-api)
- [클래스 책임 범위](#클래스-책임-범위)
- [데코레이터](#데코레이터)
- [저장 방식](#저장-방식)
- [저장 포맷 선택 근거: JSONL vs CSV](#저장-포맷-선택-근거-jsonl-vs-csv)
- [백업과 복구](#백업과-복구)
- [카테고리 삭제와 대체 전략](#카테고리-삭제와-대체-전략)
- [주요 명령 예시](#주요-명령-예시)
- [import / export CSV 스키마](#import--export-csv-스키마)
- [오류 처리](#오류-처리)
- [테스트](#테스트)
- [성능과 확장성](#성능과-확장성)
- [타입 힌트](#타입-힌트)
- [개발 환경 / 제약](#개발-환경--제약)

## 실행 방법

Python 3.10 이상이 필요합니다 (표준 라이브러리만 사용하므로 별도 설치 불필요).

```bash
python -m budget_app --help
python -m budget_app <command> --help   # 각 명령의 상세 옵션 확인
```

예:
```bash
python -m budget_app add
python -m budget_app list --limit 10
python -m budget_app summary --month 2024-01
```

데이터 저장 폴더는 기본값 `./data`이며, `--data-dir`로 변경할 수 있습니다.

```bash
python -m budget_app --data-dir ./mydata add
```

## 프로젝트 구조

```
budget_app/
  __init__.py
  __main__.py     # python -m budget_app 진입점
  models.py        # 데이터 모델 (Transaction, Category, Budget)
  exceptions.py     # 커스텀 예외 (AppError, ValidationError, NotFoundError)
  decorators.py      # 공통 관심사 데코레이터 (로그/예외처리/시간측정)
  utils.py             # 검증, 원자적 파일쓰기, id 생성
  storage.py            # 저장소(Repository) — 파일 입출력 전담
  services.py            # 서비스 — 검증 + 비즈니스 로직
  cli.py                  # argparse 기반 CLI, 명령 함수(cmd_*)
tests/
  test_services.py         # 서비스 계층 단위 테스트 (unittest)
data/                       # 실행 시 자동 생성 (저장 파일)
  transactions.jsonl
  categories.jsonl
  budgets.jsonl
  backup/<timestamp>/        # backup 명령 실행 시 생성
app.log                       # 실행 로그 (자동 생성)
```

## 아키텍처

4개 계층으로 책임을 분리했습니다. 화살표는 "알고 있는 방향"입니다 — CLI는 서비스를 알지만, 서비스는 CLI를 모릅니다.

```
CLI (cli.py) → Service (services.py) → Repository (storage.py) → Model (models.py)
```

- **CLI**: 사용자 입력(대화형 `input()` / 옵션 인자)을 받아 서비스 계층을 호출하고 결과를 출력. `argparse`로 명령/옵션 구조를 정의. 저장 방식(파일 포맷, 경로 등)을 전혀 모른다.
- **Service**: 입력 검증과 비즈니스 로직 담당. CLI는 이 계층만 호출하고, 서비스는 저장소(storage.py)만 호출한다. 검증 실패는 항상 `ValidationError`/`NotFoundError`(둘 다 `AppError`)를 던진다.
- **Repository**: 실제 파일 읽기/쓰기만 담당. 조회는 **제너레이터(yield)로 한 줄씩** 읽어 파일 전체를 메모리에 올리지 않는다. 비즈니스 규칙(예: 금액이 양수여야 한다)은 전혀 모른다 — 그건 서비스의 책임이다.
- **Model**: `dataclass`로 거래/카테고리/예산의 필드와 타입을 명확히 계약. `to_dict`/`from_dict`로 JSONL 직렬화를 캡슐화.

이렇게 나눈 이유는, 예를 들어 저장 포맷을 JSONL에서 다른 포맷으로 바꾸더라도 Repository만 고치면 되고 Service/CLI는 건드릴 필요가 없게 하기 위해서입니다. 반대로 CLI 옵션 이름을 바꾸는 건 Service/Repository에 전혀 영향을 주지 않습니다.

## 모듈별 공개 API

각 모듈에서 외부(다른 모듈)가 실제로 사용하는 공개 함수/클래스만 정리했습니다.

**`models.py`**
| 이름 | 설명 |
| --- | --- |
| `Transaction(id, type, date, amount, category, memo, tags)` | 거래 1건. `to_dict()` / `Transaction.from_dict(data)` |
| `Category(name)` | 카테고리 1건. `to_dict()` / `Category.from_dict(data)` |
| `Budget(month, amount)` | 월별 예산 1건. `to_dict()` / `Budget.from_dict(data)` |

**`exceptions.py`**
| 이름 | 설명 |
| --- | --- |
| `AppError(message, hint="")` | 모든 사용자 대상 오류의 기반 클래스 |
| `ValidationError` | 입력값 검증 실패 |
| `NotFoundError` | id/카테고리/월 등 조회 대상 없음 |

**`storage.py`**
| 이름 | 설명 |
| --- | --- |
| `TransactionRepository(path)` | `.iter_all()` `.append(tx)` `.rewrite_all(txs)` `.next_id()` |
| `CategoryRepository(path)` | `.iter_all()` `.append(cat)` `.rewrite_all(cats)` |
| `BudgetRepository(path)` | `.iter_all()` `.upsert(budget)` `.get(month)` |

**`services.py`**
| 이름 | 설명 |
| --- | --- |
| `CategoryService(repo)` | `.list_names()` `.exists(name)` `.ensure_default_categories()` `.add(name)` `.remove(name, used_categories)` |
| `TransactionService(repo, category_service)` | `.add(...)` `.list_recent(limit)` `.search(...)` `.update(tid, **fields)` `.delete(tid)` `.used_categories()` `.reassign_category(old, new)` |
| `BudgetService(repo)` | `.set_budget(month, amount)` `.get_budget(month)` |
| `SummaryService(tx_service, budget_service)` | `.monthly_summary(month, top=3) -> dict` |

**`decorators.py`**
| 이름 | 설명 |
| --- | --- |
| `track(func)` | 로그+시간측정+예외처리 데코레이터. `cmd_*` 함수에 적용 |

**`cli.py`**
| 이름 | 설명 |
| --- | --- |
| `build_services(data_dir) -> Services` | 서비스 4종 인스턴스 생성 |
| `build_parser() -> argparse.ArgumentParser` | 전체 명령/옵션 구조 정의 |
| `cmd_add, cmd_list, cmd_search, cmd_summary, cmd_budget_set, cmd_category_add/list/remove, cmd_update, cmd_delete, cmd_import, cmd_export, cmd_backup` | 명령별 핸들러. 전부 `@track` 적용, 반환값 없음(`None`) — 종료 코드는 `track`이 처리 |
| `main() -> int` | 진입점. 파싱 → 서비스 생성 → 명령 분기 → 종료 코드 반환 |

## 클래스 책임 범위

각 클래스가 어떤 상태를 들고 있고, 어디까지 바꿀 수 있는지 명시합니다.

- **`Transaction`/`Category`/`Budget`**: 상태를 갖지 않는 순수 데이터 컨테이너(dataclass)에 가깝다. 필드를 직접 바꿔도(예: `tx.amount = 100`) 파일에는 반영되지 않는다 — 반드시 Repository의 `append`/`rewrite_all`을 거쳐야 영속화된다.
- **`TransactionRepository`/`CategoryRepository`/`BudgetRepository`**: 인스턴스가 들고 있는 상태는 파일 경로(`self.path`) 하나뿐이다. 다만 `TransactionRepository`는 성능을 위해 `next_id()` 호출 결과를 프로세스 내에서만 캐시하는 내부 카운터(`self._next_seq`)를 갖는다 — 이 캐시는 파일 내용을 바꾸지 않고, 같은 프로세스 안에서 반복 호출될 때만 유효하다(자세한 이유는 [성능과 확장성](#성능과-확장성) 참고).
- **`CategoryService`/`TransactionService`/`BudgetService`/`SummaryService`**: 자체 상태는 없고(Repository 참조만 들고 있음), 매 메서드 호출마다 Repository를 통해 파일에서 다시 읽고 다시 쓴다. 따라서 서비스 인스턴스를 여러 개 만들어도 서로 상태를 공유하지 않으며, 항상 "파일에 쓰여 있는 것이 곧 진실"이다.
- **`TransactionService`가 `CategoryService`를 참조하는 이유**: 거래를 추가/수정할 때 카테고리가 실제로 등록되어 있는지 검증해야 하기 때문이다(계층을 넘지 않기 위해 Repository를 직접 참조하지 않고 서비스를 통해서만 접근한다).

## 데코레이터

`decorators.py`의 `track` 데코레이터 하나가 세 가지 공통 관심사를 전부 처리합니다. 모든 `cmd_*` 함수(`cli.py`)에 `@track`으로 적용되어 있습니다.

1. **실행 로그**: 명령 시작/종료를 `app.log`에 기록 (`[시작] cmd_add`, `[완료] cmd_add (0.003초)`)
2. **실행 시간 측정**: `time.perf_counter()`로 시작~종료 소요 시간을 재서 로그에 남김
3. **예외 처리**: `AppError`(및 그 하위 `ValidationError`/`NotFoundError`)는 `[오류] 원인` + `[힌트] 해결법`으로 표준 출력에, 그 외 예상 못 한 예외도 스택트레이스 없이 `[오류] 예상치 못한 문제가 발생했습니다: ...`로 변환해서 출력한다. 두 경우 모두 로그에도 남긴다.

세 관심사를 하나의 데코레이터로 묶은 이유는, 이 셋이 항상 "명령 하나의 시작부터 끝까지"라는 같은 생명주기를 공유하기 때문입니다(로그를 남기려면 어차피 시작/끝 시점이 필요하고, 그 시점에 시간도 같이 재고, 그 사이에서 난 예외도 같이 잡는 게 자연스럽습니다). 예시:

```python
@track
def cmd_add(args, services):
    ...
    tx = tx_service.add(...)   # 여기서 ValidationError가 나면
    print(f"[저장 완료] id={tx.id}")
# track이 자동으로 잡아서 "[오류] ..." + "[힌트] ..."로 출력하고 종료코드 1을 반환한다
```

## 저장 방식

- 포맷: **JSONL** (한 줄에 JSON 객체 하나)
- 위치: `./data` (`--data-dir`로 변경 가능), 파일 3개로 분리 저장
  - `transactions.jsonl` — 거래 내역
  - `categories.jsonl` — 카테고리 목록
  - `budgets.jsonl` — 월별 예산
- 최초 실행 시 `data/` 폴더와 파일이 자동 생성되고, 카테고리가 비어있으면 기본 카테고리(`food`, `transport`, `rent`, `etc`)가 자동으로 만들어집니다.
- **원자적 교체**: `update`/`delete`는 전체 데이터를 임시 파일(`.tmp_...`)에 다시 쓴 뒤 `os.replace`로 원자적으로 교체합니다. `os.replace`가 실행되기 **전에** 실패하면(디스크 꽉 참, 권한 오류 등) 원본 파일은 전혀 건드려지지 않은 채 그대로 남고, 임시 파일만 정리됩니다 — 즉 실패해도 데이터가 깨지거나 유실되지 않습니다. 이 실패는 `app.log`에 `[저장 실패] ... 원본을 그대로 유지합니다: <원인>`으로 기록됩니다.

## 저장 포맷 선택 근거: JSONL vs CSV

미션 요구사항은 JSONL/CSV 중 하나를 선택하는 것이었고, **내부 저장 포맷은 JSONL**을 선택했습니다(CSV는 `import`/`export`로 외부와 주고받는 교환 포맷으로만 사용).

| 비교 항목 | JSONL | CSV |
| --- | --- | --- |
| 한 줄 = 레코드 하나 (append-only, 스트리밍에 유리) | O | O |
| 가변 길이 리스트 필드(`tags`) 표현 | 네이티브 지원 (`["meal","cafe"]`) | 구분자(`,`)가 컬럼 구분자와 충돌 → 별도 이스케이프 규칙 필요 |
| 필드에 쉼표/줄바꿈/따옴표가 섞여도 안전한가 | O (JSON 문자열 이스케이프가 표준으로 처리) | 인용부호(`"`) 규칙을 직접 신경써야 함 |
| 타입 보존(정수 vs 문자열) | O (JSON 타입 그대로) | X (전부 문자열, 파싱 시 직접 변환 필요) |
| 필드 추가/변경 시 하위 호환 | 쉬움 (없는 키는 `.get()`으로 기본값 처리) | 헤더 순서/개수가 바뀌면 전체 파서 영향 |
| 사람이 코드 리뷰/diff로 한 줄만 보고 이해하기 | 비교적 쉬움 (`{"id": "TX-000001", ...}`) | 쉬움 (스프레드시트로 바로 열림) |
| 스프레드시트(Excel/Sheets)에서 바로 열어보기 | X | O |

**결론**: 이 앱의 내부 데이터는 `tags`처럼 리스트 타입 필드가 있고, `memo`에 쉼표나 특수문자가 자유롭게 들어갈 수 있어서, 이스케이프를 신경 쓰지 않아도 되는 JSONL이 더 안전합니다. 반대로 `import`/`export`는 "다른 사람이 스프레드시트로 만들어서 주고받는" 상황을 상정한 기능이므로, 그 용도에는 보편적인 CSV가 더 적합합니다 — 그래서 **저장은 JSONL, 교환은 CSV**로 용도를 나눴습니다.

## 백업과 복구

```bash
python -m budget_app backup
```

`transactions.jsonl`, `categories.jsonl`, `budgets.jsonl` 중 존재하는 파일을 `data/backup/<YYYYMMDD_HHMMSS>/` 폴더에 타임스탬프와 함께 복사합니다. 예:

```
data/backup/20240115_093000/
  transactions.jsonl
  categories.jsonl
  budgets.jsonl
```

**복구 절차** (별도 명령 없이 수동으로 파일을 되돌리는 방식입니다):

1. 복구하려는 시점의 백업 폴더를 확인합니다: `ls data/backup/`
2. 현재 파일을 원하는 백업 시점의 파일로 덮어씁니다.
   ```bash
   cp data/backup/20240115_093000/transactions.jsonl data/transactions.jsonl
   cp data/backup/20240115_093000/categories.jsonl data/categories.jsonl
   cp data/backup/20240115_093000/budgets.jsonl data/budgets.jsonl
   ```
3. `python -m budget_app list`로 정상 복구됐는지 확인합니다.

`data/` 폴더 전체(백업 포함)는 실행 시 자동 생성되는 결과물이라 `.gitignore`에 들어있어 git에는 올라가지 않습니다. 저장소 자체를 잃어버릴 위험에 대비하려면 `data/backup/`을 주기적으로 별도 스토리지(클라우드 드라이브 등)에 복사해두는 걸 권장합니다.

## 카테고리 삭제와 대체 전략

카테고리를 사용 중인 거래가 있으면 기본적으로 삭제가 막힙니다.

```bash
$ python -m budget_app category remove --name food
[오류] 'food' 카테고리를 사용 중인 거래가 있어 삭제할 수 없습니다.
[힌트] update로 거래를 하나씩 옮기거나, --replace-with <대체카테고리>로 한 번에 옮기세요.
```

한 건씩 `update --id <id> --category <새카테고리>`로 옮길 수도 있지만, 거래가 많으면 번거롭습니다. 이럴 때 `--replace-with`로 **그 카테고리를 쓰는 모든 거래를 한 번에 다른 카테고리로 이관한 뒤** 삭제할 수 있습니다.

```bash
$ python -m budget_app category remove --name food --replace-with etc
[안내] 3건의 거래를 'etc' 카테고리로 이관했습니다.
[삭제 완료] category=food
```

`--replace-with`로 지정한 카테고리가 존재하지 않거나, 삭제할 카테고리와 같으면 이관 전에 오류로 막습니다(중간에 절반만 이관되는 상태가 생기지 않도록, 검증을 전부 통과한 뒤에만 실제 이관을 수행합니다).

## 주요 명령 예시

```bash
# 거래 추가 (대화형)
$ python -m budget_app add
날짜(YYYY-MM-DD): 2024-01-15
타입(income/expense): expense
카테고리: food
금액(양수): 15000
메모(선택): 점심
태그(쉼표로 구분, 없으면 엔터): meal
[저장 완료] id=TX-000001

# 목록 조회
$ python -m budget_app list --limit 3
TX-000001 | 2024-01-15 | expense | food | 15000 | 점심 | meal

# 검색
$ python -m budget_app search --category food --type expense --from 2024-01-01 --to 2024-01-31

# 월별 요약
$ python -m budget_app summary --month 2024-01 --top 3
총 수입: 3000000원
총 지출: 215000원
잔액: 2785000원
예산: 500000원 (사용률 43.0%)

지출 TOP 3
1) rent 150000원
2) food 45000원
3) transport 20000원

# 예산 설정
$ python -m budget_app budget set --month 2024-01 --amount 500000

# 카테고리 관리
$ python -m budget_app category add
$ python -m budget_app category list
$ python -m budget_app category remove --name etc
$ python -m budget_app category remove --name food --replace-with etc   # 사용 중이어도 이관 후 삭제

# 수정 / 삭제
$ python -m budget_app update --id TX-000001 --amount 18000 --memo 점심수정
$ python -m budget_app delete --id TX-000001

# CSV 내보내기 / 가져오기
$ python -m budget_app export --out export.csv --month 2024-01
$ python -m budget_app import --from import.csv

# 백업
$ python -m budget_app backup
[완료] 백업 생성: ./data/backup/20240115_093000 (3개 파일)
```

## import / export CSV 스키마

| column | required | 설명 |
| --- | --- | --- |
| date | Y | YYYY-MM-DD |
| type | Y | income / expense |
| category | Y | 등록된 카테고리 |
| amount | Y | 양수 정수 |
| memo | N | 문자열 |
| tags | N | 쉼표(,) 구분 문자열 |

인코딩은 UTF-8, 첫 줄은 헤더입니다. `export`는 `--month YYYY-MM` 또는 `--from/--to` 중 하나 이상의 조건이 필수입니다.

`import`는 형식에 맞지 않거나(날짜 형식 오류, 존재하지 않는 카테고리, 금액이 숫자가 아님 등) 필수 컬럼이 없는 행은 건너뛰고, 처리 결과를 `imported=N, skipped=M`으로 출력합니다. **건너뛴 행이 있으면** 어느 행(CSV 파일 기준 줄 번호, 헤더=1행)이 왜 걸렸는지를 `app.log`에 `WARNING` 레벨로 남깁니다 — CLI 표준 출력에는 총 건수만 보여주고(콘솔이 지저분해지지 않도록), 상세 사유는 로그 파일에서 확인하는 구조입니다.

```
[완료] imported=8, skipped=2
[안내] 건너뛴 행의 상세 사유는 app.log에서 확인할 수 있습니다.
```
```
# app.log
2024-01-15 09:30:00,123 WARNING [import 건너뜀] import.csv 3행: 날짜 형식이 올바르지 않습니다: 2024-13-40
2024-01-15 09:30:00,124 WARNING [import 건너뜀] import.csv 7행: 등록되지 않은 카테고리입니다: 여행
```

## 오류 처리

- 잘못된 입력(날짜 형식, 0 이하 금액, 존재하지 않는 카테고리/id 등)은 파이썬 스택트레이스 대신 `[오류] 원인` + `[힌트] 해결 방법` 형태로 출력합니다.
- **메시지 컨벤션 중앙화**: 모든 사용자 대상 오류는 `exceptions.py`의 `AppError(message, hint)` 하나의 형태로 표현되고, 실제 출력 문구 조립(`[오류] ...` / `[힌트] ...`)은 `decorators.py`의 `track` 한 곳에서만 이루어집니다. 즉 서비스 계층 코드 곳곳에서 `print`를 흩뿌리지 않고, "무엇이 잘못됐는지"만 예외로 던지면 "어떻게 보여줄지"는 항상 같은 한 곳에서 일관되게 처리됩니다.
- **종료 코드 규약**: 모든 `cmd_*` 함수는 값을 반환하지 않습니다(`-> None`). 종료 코드는 오직 `track` 데코레이터가 결정합니다 — 정상 종료 시 `0`, `AppError` 또는 예상 못 한 예외 발생 시 `1`. `main()`은 `cmd_*` 호출 결과(이미 0/1로 변환된 값)를 그대로 반환하고, `__main__.py`가 `sys.exit(main())`으로 프로세스 종료 코드에 반영합니다.
- 모든 명령의 실행 로그(시작/완료/오류, 소요 시간)는 `app.log`에 기록됩니다.

## 테스트

`tests/test_services.py`에 서비스 계층 단위 테스트가 있습니다(`unittest`, 표준 라이브러리만 사용, 총 18개).

```bash
python -m unittest discover -s tests -t .
```

각 테스트는 `tempfile.TemporaryDirectory()`로 임시 데이터 폴더를 만들어 실행하므로 실제 `./data`를 건드리지 않습니다. 주요 커버리지:

- 거래 추가 검증: 잘못된 날짜, 0 이하 금액, 존재하지 않는 카테고리 거부
- id가 `TX-000001`부터 순차 발급되고 실제로 파일에 저장되는지
- 존재하지 않는 id로 update/delete 시 `NotFoundError`
- 카테고리 중복 추가 거부, 사용 중인 카테고리 삭제 차단
- `reassign_category`로 카테고리 일괄 이관 후 정상 삭제되는 흐름 (`category remove --replace-with`가 내부적으로 쓰는 것과 동일한 경로)
- **예산 사용률·초과 경고**: 예산 설정 후 지출이 예산의 40%일 때 `usage_rate == 40.0`이고 `over_budget == False`, 지출이 예산을 넘으면(150%) `over_budget == True`가 되는지
- 같은 달에 예산을 두 번 설정하면 덮어쓰기(upsert)되는지
- 월별 요약의 카테고리 TOP N이 지출 합계 내림차순으로 정렬되는지
- 데이터가 없는 달을 조회하면 `has_data == False`인지

## 성능과 확장성

> 아래는 대략 10만 건 규모를 가정했을 때의 병목 분석과 개선 방향입니다. 일부(①)는 실측 후 실제로 코드에 반영했고, 나머지(②③④)는 현재 미션의 "JSONL 또는 CSV 중 1개, 파일 3개"라는 제약을 지키는 선에서는 근본적으로 해결하기 어려운 구조적 한계라, 분석과 제안만 정리했습니다.

**① `next_id()` 반복 스캔 — 실제로 발견해서 수정함**

기존 구현은 거래를 추가할 때마다 `transactions.jsonl` 전체를 다시 읽어 최대 id를 계산했습니다. `add` 한 번이면 문제없지만, `import`로 대량 등록할 때는 N번째 행마다 N개를 다시 읽는 꼴이라 **O(n²)**이 됩니다. 실제로 측정해보니:

| 건수 | 개선 전 (매번 전체 재스캔) | 개선 후 (프로세스 내 id 캐시) |
| --- | --- | --- |
| 3,000건 add | 16.43초 | 0.15초 |
| 20,000건 add | (측정 안 함, 외삽 시 수백 초 이상) | 0.99초 |
| 5,000행 CSV `import` (CLI 전체) | (외삽 시 약 45초) | 0.35초 |

수정 방법은 `TransactionRepository`가 `next_id()`를 처음 호출할 때만 파일을 스캔해 마지막 순번을 구하고, 이후에는 프로세스 메모리에서 1씩 증가시키는 것입니다(`storage.py`의 `_next_seq` 캐시). 캐시는 파일 내용이 아니라 "이번 프로세스에서 지금까지 발급한 번호"만 기억하므로, 명령을 새로 실행하면(=새 프로세스) 다시 파일에서 정확하게 다시 계산합니다 — 그래서 안전합니다. 10만 건 단위 `import` 한 번에서 효과가 가장 큽니다.

**② `update`/`delete`의 전체 파일 재작성**

`update`/`delete`는 매번 파일 전체를 메모리로 읽고, 전체를 다시 써서 원자적으로 교체합니다. 10만 건 규모에서 거래 1건을 수정할 때마다 10만 줄을 통째로 다시 쓰는 셈이라, 수정/삭제가 잦아질수록 느려집니다.
- **개선 방향(미구현, 제안)**: id → 파일 내 byte offset을 기록하는 별도 인덱스를 두고 해당 위치만 덮어쓰거나, 표준 라이브러리인 `sqlite3`로 전환해 실제 인덱스 기반 갱신을 사용하는 방법이 있습니다. 다만 이 미션은 "JSONL 또는 CSV 중 1개"를 저장 포맷으로 요구하므로, sqlite3 전환은 현재 범위를 벗어난 더 큰 설계 변경입니다.

**③ `list`/`search`의 전체 로드 후 정렬**

`list_recent`/`search`는 조건에 맞는 거래를 제너레이터로 걸러내긴 하지만, 최신순 정렬을 위해 결과를 리스트로 모은 뒤 `sort()`를 호출합니다. 조건에 맞는 결과가 적으면 문제없지만, 조건 없이 `list`만 호출해도 내부적으로 전체를 훑고 정렬합니다.
- **개선 방향(미구현, 제안)**: JSONL이 항상 추가된 순서(오래된→최신)로 쌓인다는 특성을 이용해, 파일을 뒤에서부터 읽어 필요한 개수(`--limit`)만큼만 확보하면 정렬 자체가 필요 없어집니다. `collections.deque(maxlen=N)`으로 마지막 N개만 유지하며 스트리밍하는 방식이 바로 적용 가능합니다.
- **소비자(호출하는 쪽) 권장사항**: 지금도 `list --limit`, `summary --top` 옵션이 있으므로, 대량 데이터에서는 기본값(무제한 대신 작은 limit)을 쓰는 것이 실질적인 완화책입니다. 전체 내보내기가 필요하면 `export`로 CSV를 만들어 스프레드시트/별도 도구에서 처리하는 걸 권장합니다.

**④ `summary`의 월 무관 전체 스캔**

`monthly_summary`는 요청한 달과 무관하게 `transactions.jsonl` 전체를 읽고 나서 날짜 접두사로 걸러냅니다. 10만 건이 여러 해에 걸쳐 쌓여 있어도 한 달치 요약을 위해 매번 전체를 읽습니다.
- **개선 방향(미구현, 제안)**: 월별로 파일을 분리(`transactions/2024-01.jsonl` 등)하면 해당 월 파일만 읽으면 되지만, 이 역시 "파일 3개로 분리"라는 현재 미션 제약과는 다른 설계이므로 제안으로만 남깁니다.

**병렬화에 대해**: 위 병목은 대부분 디스크에서 파일을 순차로 읽는 I/O 작업이지, CPU 연산이 오래 걸리는 게 아닙니다. 따라서 멀티프로세싱으로 CPU 코어를 늘리는 접근보다는, 애초에 읽어야 할 데이터량 자체를 줄이는 것(①②③④의 인덱싱/캐싱/파티셔닝)이 더 근본적인 해결책이라고 판단했습니다. 다만 `import`처럼 각 행의 검증이 서로 독립적인 대량 작업이라면, 여러 스레드가 CSV를 나눠 검증하고 마지막에 한 스레드만 파일에 쓰는 방식으로 I/O 대기 시간을 겹치게 할 여지는 있습니다(단, 표준 라이브러리 `threading` 사용 시 실제 이득은 검증 로직이 I/O를 얼마나 기다리는지에 달려 있어, 이 앱처럼 검증이 대부분 메모리 연산인 경우 효과가 제한적일 수 있습니다).

## 타입 힌트

모든 공개 함수/메서드에 매개변수·반환 타입을 명시했습니다. 특히 CLI 계층(`cli.py`)의 모든 `cmd_*` 핸들러는 `(args: argparse.Namespace, services: Services) -> None` 형태로 통일했습니다 — 여기서 `Services`는 `Tuple[TransactionService, CategoryService, BudgetService, SummaryService]`의 타입 별칭으로, 서비스 4종을 주고받는 계약을 한 곳에서 정의합니다.

## 개발 환경 / 제약

- Python 3.10 이상, 표준 라이브러리만 사용 (외부 패키지 설치 불필요 — 테스트도 `unittest`만 사용)
- 옵션 표기는 `--`(예: `--limit`, `--from`, `--month`)로 통일