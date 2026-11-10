# 나만의 용돈 기입장

Python **표준 라이브러리만**으로 만든 파일 기반 콘솔 가계부입니다.
거래 추가/조회/검색/수정/삭제, 월별 요약, 카테고리·예산 관리, CSV 가져오기/내보내기, 백업, 반복 내역을 지원합니다.

## 평가문항별 바로가기

| 평가 항목 | 확인할 곳 |
| --- | --- |
| 항목 1. 기능 동작 / 데이터 유지 / 오류 처리 / 종료 코드 | [실행 방법](#1-실행-방법) → [기능별 실행 방법](#2-기능별-실행-방법-하나씩) → [저장 정책](#3-저장-정책) → [CSV 스키마](#4-import--export-csv-스키마) → [오류 처리와 종료 코드](#10-오류-처리와-종료-코드) |
| 항목 2. 모듈/클래스 구조, update/delete 안전성 | [구조 설명](#5-구조-설명-항목-2) |
| 항목 3. 제너레이터 / 데코레이터 / 타입 힌트 | [제너레이터](#6-1-제너레이터로-스트리밍-처리) · [데코레이터](#6-2-데코레이터로-공통-기능-분리) · [타입 힌트](#6-3-타입-힌트) |
| 항목 4. JSONL vs CSV / 10만 건 / 깨진 CSV 행 | [저장 포맷 선택](#7-1-jsonl-vs-csv--왜-jsonl인가) · [10만 건 분석](#7-2-거래가-10만-건이-되면) · [import 신뢰성](#7-3-import-csv에-깨진-행이-섞이면) |
| 항목 5. 보너스 | [보너스](#8-보너스-과제) |

---

## 1. 실행 방법

**Python 3.10 이상**이 필요합니다. 외부 패키지 설치는 필요 없습니다.

> **`python`이 아니라 `python3`로 실행하세요.** macOS/Linux에는 `python` 명령이 없는 환경이 많아서(`command not found: python`), 이 README의 모든 명령은 `python3`로 적었습니다.

```bash
# 0) 버전 확인 (3.10 이상이어야 함)
python3 --version

# 1) 내려받기
git clone https://github.com/yj-min-i/codyssey-B2-1.git
cd codyssey-B2-1          # ← budget_app/ 폴더가 보이는 위치(저장소 루트)에서 실행해야 합니다

# 2) 도움말 (모든 명령은 --help 지원)
python3 -m budget_app --help
python3 -m budget_app add --help

# 3) 실행 형식
python3 -m budget_app <command> [options]
```

주의할 점 세 가지:

- 반드시 **저장소 루트**(`budget_app/` 폴더가 있는 곳)에서 실행합니다. 다른 폴더에서는 `No module named budget_app` 오류가 납니다.
- 데이터 저장 폴더는 기본 `./data` (실행한 위치 기준)이며, **`--data-dir`는 명령 이름 앞에** 적습니다.
  ```bash
  python3 -m budget_app --data-dir ./mydata add      # O
  python3 -m budget_app add --data-dir ./mydata      # X (argparse 오류, 종료 코드 2)
  ```
- 실행 로그는 실행한 폴더의 `app.log`에 쌓입니다. (`data/`, `app.log`, `export.csv`는 `.gitignore` 대상)

테스트 실행(표준 라이브러리 `unittest`, 총 33개):

```bash
python3 -m unittest discover -s tests -t .
```

---

## 2. 기능별 실행 방법 (하나씩)

아래 순서대로 따라 하면 모든 기능을 확인할 수 있습니다. 출력은 실제로 실행한 결과입니다. 각 명령 뒤에 `echo $?`를 붙이면 종료 코드(성공 0 / 오류 1)를 볼 수 있습니다.

### 2-0. 최초 실행 (저장 파일 자동 생성)

```bash
$ python3 -m budget_app list
데이터 없음
$ ls data
budgets.jsonl  categories.jsonl  transactions.jsonl

$ python3 -m budget_app category list
- food
- transport
- rent
- etc
```

저장 파일이 없으면 **자동 생성**하고, 카테고리 파일이 비어 있으면 **기본 카테고리 4개(`food, transport, rent, etc`)를 자동 생성**합니다(미션의 "안 A"). 

### 2-1. 카테고리 관리 `category add / list / remove`

```bash
$ python3 -m budget_app category add          # 대화형
카테고리명: study
[저장 완료] category=study

$ python3 -m budget_app category list
- food
- transport
- rent
- etc
- study
```

**삭제** — 사용 중인 카테고리는 그냥 지울 수 없고, 대체 카테고리를 요구합니다(삭제 막기 + 대체 요구).

```bash
$ python3 -m budget_app category remove --name food
[오류] 'food' 카테고리를 사용 중입니다.
[힌트] --replace-with 옵션으로 대체 카테고리를 지정하세요.

$ python3 -m budget_app category remove --name food --replace-with etc
[안내] 일반 거래 2건, 반복 규칙 0건을 이관했습니다.
[삭제 완료] category=food

$ python3 -m budget_app category remove --name study      # 사용 중이 아니면 바로 삭제
[삭제 완료] category=study

$ python3 -m budget_app category remove --name ghost
[오류] 존재하지 않는 카테고리입니다: ghost
[힌트] category list로 등록된 카테고리를 확인하세요.
```

### 2-2. 거래 추가 `add` (대화형 입력)

```bash
$ python3 -m budget_app add
날짜(YYYY-MM-DD): 2026-11-02
타입(income/expense): expense
카테고리: food
금액(양수): 15000
메모(선택): 점심
태그(쉼표로 구분, 없으면 엔터): meal
[저장 완료] id=TX-000002
```

날짜 형식 오류, 0 이하 금액, 허용되지 않은 type, 등록되지 않은 category는 오류 메시지로 거부합니다(→ [2-10](#2-10-잘못된-입력--오류--종료-코드-확인)).

### 2-3. 거래 목록 `list`

```bash
$ python3 -m budget_app list --limit 3        # 최신순, 기본값 10
TX-000005  | 2026-11-06 | expense | food       |     30000 | 저녁 | meal,friends
TX-000004  | 2026-11-05 | expense | rent       |    150000 | 월세
TX-000003  | 2026-11-03 | expense | transport  |     20000 | 교통카드
```

컬럼(`id | date | type | category | amount | memo | tags`)은 문자열 정렬(`ljust`/`rjust`)로 칸을 맞춥니다.

### 2-4. 거래 검색 `search`

모든 조건은 선택이며 함께 쓰면 AND로 적용됩니다. 결과는 최신순입니다.

```bash
$ python3 -m budget_app search --category food --type expense --from 2026-11-01 --to 2026-11-30
TX-000005  | 2026-11-06 | expense | food       |     30000 | 저녁 | meal,friends
TX-000002  | 2026-11-02 | expense | food       |     15000 | 점심 | meal

$ python3 -m budget_app search --q 점심        # 메모 키워드
$ python3 -m budget_app search --tag meal      # 태그
```

| 옵션 | 의미 |
| --- | --- |
| `--from`, `--to` | 기간(YYYY-MM-DD). 시작일이 종료일보다 늦으면 오류 |
| `--category` | 카테고리 |
| `--type` | `income` / `expense` |
| `--q` | 메모에 포함된 키워드 |
| `--tag` | 태그 |

### 2-5. 예산 설정 `budget set` + 월별 요약 `summary`

```bash
$ python3 -m budget_app budget set --month 2026-11 --amount 500000
[저장 완료] 2026-11 예산 500000원

$ python3 -m budget_app summary --month 2026-11 --top 3
총 수입: 3000000원
총 지출: 215000원
잔액: 2785000원
예산: 500000원 (사용률 43.0%)

지출 TOP 3
1) rent 150000원
2) food 45000원
3) transport 20000원
```

예산을 지출보다 낮게 다시 설정하면 **초과 경고**가 나옵니다(같은 달 예산은 덮어쓰기).

```bash
$ python3 -m budget_app budget set --month 2026-11 --amount 100000
$ python3 -m budget_app summary --month 2026-11 --top 2
...
예산: 100000원 (사용률 215.0%)
[경고] 이번 달 예산을 초과했습니다!
```

데이터가 없는 달은 `데이터 없음`을 출력합니다(`summary --month 2026-12`). 예산은 `data/budgets.jsonl`에 저장되어 재실행해도 유지됩니다.

### 2-6. 거래 수정 `update` — **옵션 방식(안 A)으로 고정**

`--id`로 대상을 정하고, 바꿀 필드만 옵션으로 지정합니다. 지정하지 않은 필드는 그대로 유지됩니다. (대화형 수정은 제공하지 않습니다.)

```bash
$ python3 -m budget_app update --id TX-000002 --amount 18000 --memo 점심수정
[수정 완료] id=TX-000002

$ python3 -m budget_app update --id TX-999999 --amount 1
[오류] 존재하지 않는 거래 id입니다: TX-999999
[힌트] list 또는 search로 거래 id를 확인하세요.

$ python3 -m budget_app update --id TX-000002          # 바꿀 항목이 하나도 없으면
[오류] 수정할 항목이 지정되지 않았습니다.
[힌트] 예: update --id TX-000001 --amount 15000
```

사용 가능한 옵션: `--date --type --category --amount --memo --tags(쉼표 구분)`. 수정한 값도 `add`와 같은 검증을 다시 거칩니다.

### 2-7. 거래 삭제 `delete`

```bash
$ python3 -m budget_app delete --id TX-000003
[삭제 완료] id=TX-000003

$ python3 -m budget_app delete --id TX-000003      # 이미 없는 id
[오류] 존재하지 않는 거래 id입니다: TX-000003
[힌트] list 또는 search로 거래 id를 확인하세요.
```

### 2-8. CSV 내보내기 / 가져오기 `export` / `import`

```bash
# 내보내기: --month 또는 --from/--to 중 하나 이상 필수
$ python3 -m budget_app export --out export.csv --month 2026-11
[완료] export.csv (4 records)
$ python3 -m budget_app export --out range.csv --from 2026-11-01 --to 2026-11-15

$ python3 -m budget_app export --out x.csv            # 조건 없음
[오류] export는 --month 또는 --from/--to 조건이 필요합니다.
[힌트] 예: export --out out.csv --month 2024-01

# 가져오기
$ python3 -m budget_app import --from import.csv
[완료] imported=1, skipped=2
[안내] 건너뛴 행의 상세 사유는 app.log에서 확인할 수 있습니다.
```

`export`로 만든 파일은 그대로 `import`에 쓸 수 있습니다(같은 스키마). 스키마는 [4번](#4-import--export-csv-스키마), 깨진 행 처리 방식은 [7-3](#7-3-import-csv에-깨진-행이-섞이면)을 보세요.

### 2-9. 저장된 데이터가 재실행 후에도 유지되는지 확인

```bash
$ python3 -m budget_app add          # 거래 1건 추가
$ python3 -m budget_app budget set --month 2026-11 --amount 500000
$ python3 -m budget_app category add # 카테고리 1개 추가
# ↑ 프로그램은 매번 종료됩니다. 아래는 모두 '새 프로세스'로 다시 읽은 결과입니다.
$ python3 -m budget_app list
$ python3 -m budget_app category list
$ python3 -m budget_app summary --month 2026-11
$ wc -l data/*.jsonl                  # 저장 파일 3개(+ recurring.jsonl)에 줄이 남아 있음
```

저장 파일은 `data/transactions.jsonl`, `data/categories.jsonl`, `data/budgets.jsonl` **3개**입니다(반복 내역을 쓰면 `recurring.jsonl`이 추가됩니다). 자동 테스트(`tests/test_cli.py`의 `PersistenceTests`)도 같은 확인을 합니다.

### 2-10. 잘못된 입력 / 오류 / 종료 코드 확인

잘못된 입력은 파이썬 오류 화면(스택트레이스) 대신 `[오류] 원인` + `[힌트] 해결 방법`으로 출력됩니다.

```bash
$ python3 -m budget_app add
날짜(YYYY-MM-DD): 2024-13-40
타입(income/expense): expense
카테고리: etc
금액(양수): 1000
메모(선택):
태그(쉼표로 구분, 없으면 엔터):
[오류] 날짜 형식이 올바르지 않습니다: 2024-13-40
[힌트] 예: 2024-01-15 (YYYY-MM-DD)

$ python3 -m budget_app summary --month 2026-13
[오류] 존재하지 않는 월입니다: 2026-13
[힌트] 01부터 12 사이의 월을 입력하세요.

$ python3 -m budget_app import --from nope.csv
[오류] 파일을 찾을 수 없습니다: nope.csv
[힌트] 경로를 확인하세요. 예: import --from ./import.csv
```

**종료 코드 확인** — 직전 명령의 종료 코드는 `echo $?`로 볼 수 있습니다.

```bash
$ python3 -m budget_app list --limit 3 ; echo "exit code: $?"
...
exit code: 0            # 성공

$ python3 -m budget_app delete --id TX-999999 ; echo "exit code: $?"
[오류] 존재하지 않는 거래 id입니다: TX-999999
[힌트] list 또는 search로 거래 id를 확인하세요.
exit code: 1            # 오류 → 0이 아님
```

### 2-11. 백업 `backup` (보너스)

```bash
$ python3 -m budget_app backup
[완료] 백업 생성: ./data/backup/20261107_213542 (4개 파일)
```

### 2-12. 반복 내역 `recurring` (보너스)

```bash
$ python3 -m budget_app recurring add
타입(income/expense): income
카테고리: etc
금액(양수): 3000000
매달 생성일(1~28): 25
메모(선택): 월급
태그(쉼표로 구분, 없으면 엔터): salary
[저장 완료] 매달 25일 etc 3000000원(income)

$ python3 -m budget_app recurring list
income | etc | 3000000원 | 매달 25일 | 월급

$ python3 -m budget_app recurring apply --month 2026-12
[완료] 2026-12에 반복 거래 1건을 생성했습니다.
$ python3 -m budget_app recurring apply --month 2026-12      # 같은 달 재실행
[완료] 2026-12에 반복 거래 0건을 생성했습니다.
```

---

## 3. 저장 정책

| 항목 | 내용 |
| --- | --- |
| 포맷 | **JSONL** (한 줄 = JSON 객체 1개, UTF-8) |
| 위치 | `./data` (실행한 폴더 기준). `--data-dir`로 변경 |
| 파일 | `transactions.jsonl`(거래) · `categories.jsonl`(카테고리) · `budgets.jsonl`(월 예산) · `recurring.jsonl`(반복 규칙, 보너스) |
| 최초 실행 | 폴더·파일 자동 생성. 카테고리가 비어 있으면 기본 4개 자동 생성(안 A) |

실제 저장 모습:

```
# data/transactions.jsonl
{"id": "TX-000002", "type": "expense", "date": "2026-11-02", "amount": 18000, "category": "etc", "memo": "점심수정", "tags": ["meal"]}
# data/categories.jsonl
{"name": "transport"}
# data/budgets.jsonl
{"month": "2026-11", "amount": 100000}
```

거래 모델(`Transaction`)의 필드: `id`(유일, `TX-000001` 형식), `type`(income/expense), `date`(YYYY-MM-DD), `amount`(양수 정수), `category`, `memo`(선택), `tags`(선택, 리스트).

---

## 4. import / export CSV 스키마

| column | required | 설명 |
| --- | --- | --- |
| date | Y | YYYY-MM-DD |
| type | Y | income / expense |
| category | Y | 등록된 카테고리 |
| amount | Y | 양수 정수 |
| memo | N | 문자열 |
| tags | N | 쉼표(,) 구분 문자열 (쉼표가 있으면 `"meal,friends"`처럼 따옴표로 감쌈) |
| 공통 | | **UTF-8, 첫 줄은 헤더** |

예시 (`export`가 실제로 만든 파일):

```csv
date,type,category,amount,memo,tags
2026-11-06,expense,etc,30000,저녁,"meal,friends"
2026-11-05,expense,rent,150000,월세,
2026-11-01,income,etc,3000000,용돈,allowance
```

- `import`는 필수 헤더(`date,type,category,amount`) 중 하나라도 없으면 파일 전체를 거부하고 어떤 헤더가 빠졌는지 알려줍니다.
- 엑셀의 "CSV UTF-8" 저장본처럼 맨 앞에 BOM이 붙은 파일도 읽을 수 있습니다(`utf-8-sig`).

---

## 5. 구조 설명

### 5-1. 모듈 분리 — 8개 파일, 각자 하나의 책임

| 모듈 | 책임 | 알고 있는 것 / 모르는 것 |
| --- | --- | --- |
| `models.py` | 데이터의 모양: `Transaction`, `Category`, `Budget`, `RecurringRule` (`dataclass`) + `to_dict`/`from_dict` | 파일·CLI를 모름 |
| `exceptions.py` | 사용자에게 보여줄 오류: `AppError(message, hint)` → `ValidationError`, `NotFoundError` | 출력 방법을 모름 |
| `utils.py` | 공용 도구: 날짜/월 검증, **원자적 파일 쓰기**, id 채번 | 업무 규칙을 모름 |
| `storage.py` | **파일 읽기/쓰기만** (Repository 4종) | "금액은 양수" 같은 규칙을 모름 |
| `services.py` | **업무 규칙과 입력 검증** (Service 5종) | 파일 형식·CLI 옵션을 모름 |
| `decorators.py` | 공통 관심사(`track`): 로그·시간 측정·예외 처리 | 업무 로직을 모름 |
| `cli.py` | `argparse`, `input()`, 출력 | 저장 방식을 모름 |
| `__main__.py` | `python3 -m budget_app` 진입점 | |

**어떻게 나눴나** — "무엇이 바뀔 때 어디를 고치는가"를 기준으로 잘랐습니다.

```
CLI (cli.py) ──▶ Service (services.py) ──▶ Repository (storage.py) ──▶ Model (models.py)
        └────── track 데코레이터(decorators.py)가 모든 cmd_* 를 감쌈 ──────┘
```

- 옵션 이름을 바꾸면 `cli.py`만 고칩니다.
- "금액은 양수여야 한다"는 규칙이 바뀌면 `services.py`만 고칩니다.
- JSONL을 다른 포맷으로 바꾸면 `storage.py`만 고칩니다.
- 의존 방향은 한쪽입니다. CLI는 서비스를 알지만 서비스는 CLI를 모르고, 서비스는 저장소를 알지만 저장소는 서비스를 모릅니다.

### 5-2. 클래스 책임 경계 — 어떻게 정했나

핵심 규칙은 두 가지입니다. **① 파일을 만지는 클래스와 규칙을 판단하는 클래스를 분리**하고, **② 다른 영역의 데이터가 필요하면 그 영역의 서비스에 물어본다**(저장소를 직접 열지 않는다).

| 경계 | 한쪽의 책임 | 다른 쪽의 책임 | 경계가 보이는 코드 |
| --- | --- | --- | --- |
| `TransactionService` ↔ `TransactionRepository` | 입력 검증, id 발급 요청, 수정·삭제 흐름 | 줄 단위 읽기/쓰기, 원자적 교체, id 캐시 | 서비스는 `self.repo.append(tx)`만 호출. 파일 경로·JSON 변환은 저장소 안에서만 처리 |
| `TransactionService` ↔ `CategoryService` | 거래의 category가 유효한지 *검증* | 카테고리 목록/존재 여부의 *진실* | 거래 검증 시 `self.category_service.exists(category)`로 질의 (카테고리 파일을 직접 열지 않음) |
| `SummaryService` ↔ `TransactionService`/`BudgetService` | 합계·잔액·TOP N·사용률 *계산* | 거래·예산 데이터 *제공* | `SummaryService`는 `tx_service.iter_all()`, `budget_service.get_budget()`만 사용 |
| `RecurringService` ↔ `TransactionService` | 규칙 관리, "이미 만든 달" 기록 | 실제 거래 생성·검증 | 규칙 적용 시 `tx_service.add(...)`를 그대로 재사용 → 반복 거래도 일반 거래와 같은 검증 통과 |

상태 규칙도 정해 두었습니다.

- 모델(`dataclass`)은 데이터 컨테이너일 뿐이라 필드를 바꿔도 파일에는 반영되지 않습니다. 반드시 저장소의 `append`/`rewrite_all`을 거쳐야 저장됩니다.
- 서비스는 자체 상태 없이 매 호출마다 파일에서 읽습니다. **"파일에 쓰여 있는 것이 곧 진실"**이라서 서비스 인스턴스끼리 상태가 어긋날 일이 없습니다.
- 유일한 예외는 `TransactionRepository._next_seq`(id 발급 카운터)입니다. 같은 프로세스 안에서만 쓰는 캐시이고, 새로 실행하면 파일에서 다시 계산합니다([7-2](#7-2-거래가-10만-건이-되면) ①).

### 5-3. 파일 기반 update/delete를 안전하게 처리한 방법

JSONL은 "중간 한 줄만 고치기"가 안 되므로 update/delete는 **전체를 다시 쓰는** 작업입니다. 쓰는 도중 실패해도 원본이 깨지지 않도록 `utils.atomic_write_lines`에서 다음 순서로 처리합니다.

1. 원본과 **같은 폴더에** 임시 파일을 만든다 (`tempfile.mkstemp(dir=원본 폴더, prefix=".tmp_")`). 같은 파일시스템이어야 교체가 원자적으로 동작합니다.
2. 새 내용을 **임시 파일에만** 전부 쓴다. 이 단계에서 실패(디스크 부족, 권한 등)해도 원본은 건드리지 않았습니다.
3. 다 쓴 뒤에만 `os.replace(임시, 원본)`으로 한 번에 교체한다. 이 교체는 "옛 파일이거나 새 파일이거나" 둘 중 하나로만 보입니다(반쯤 쓰인 파일이 보이지 않음).
4. 실패하면 임시 파일을 지우고, 원인을 `app.log`에 `[저장 실패] ... 원본을 그대로 유지합니다`로 남긴 뒤 오류를 사용자에게 알립니다.

그 밖의 안전장치:

- **검증이 먼저, 쓰기는 나중**: `update`는 새 값을 모두 검증한 뒤에만 쓰므로, 잘못된 값으로 파일을 덮어쓰는 일이 없습니다.
- **존재하지 않는 id**는 파일을 건드리기 전에 `NotFoundError`로 끝냅니다(`delete`는 지운 뒤 개수가 그대로면 오류).
- **여러 파일에 걸친 작업**(`category remove --replace-with`)은 `반복 규칙 이관 → 거래 이관 → 카테고리 삭제` 순서로 진행합니다. 파일마다는 원자적이지만 파일 *사이*는 트랜잭션이 아니라서, 중간에 끊겨도 **같은 명령을 다시 실행하면 이어서 완료**되도록(이미 옮긴 것은 0건으로 건너뜀) 순서를 정했습니다.
- 한계: 정전 직후의 내용까지 보장하려면 `fsync`가 필요한데 쓰지 않았고, 두 프로세스가 동시에 쓰는 경우를 막는 파일 잠금도 없습니다. 개인용 단일 프로세스 사용을 전제로 했습니다.

---

## 6. 제너레이터 · 데코레이터 · 타입 힌트

### 6-1. 제너레이터로 스트리밍 처리

**어떻게 구현했나** — `storage.py`의 `iter_all()`이 파일을 한 줄씩 읽고 `yield`로 객체를 하나씩 내보냅니다.

```python
def iter_all(self) -> Iterator[Transaction]:
    _ensure_file(self.path)
    with open(self.path, "r", encoding="utf-8") as f:
        for line in f:                       # 파일 전체가 아니라 한 줄씩
            ...
            yield Transaction.from_dict(data)   # 호출자가 달라고 할 때 하나씩
```

- `list`: `heapq.nlargest(limit, repo.iter_all(), key=(date, id))` — 흘러오는 거래 중 **최신 N개만** 들고 있습니다.
- `search`: 제너레이터를 `for`로 훑으면서 조건에 맞는 것만 결과에 담습니다.
- `summary`: 제너레이터를 한 번 훑으면서 합계만 누적합니다.

**왜 유리한가** — 파일 크기와 상관없이 메모리를 일정하게 씁니다. 100,000건(13.8 MB 파일)에서 `tracemalloc`으로 측정한 최대 메모리 사용량입니다.

| 방식 | 최대 메모리 | 시간 |
| --- | --- | --- |
| 제너레이터로 순회 (`sum(1 for _ in repo.iter_all())`) | **0.03 MB** | 1.33초 |
| `list(repo.iter_all())`로 전부 올림 | **48.00 MB** | 1.89초 |
| `list --limit 10` 방식 (`nlargest`) | **0.03 MB** | 1.41초 |

(측정 환경: Python 3.13, `tracemalloc` 켠 상태라 시간은 실제보다 느립니다. 숫자는 환경에 따라 달라지지만 "일정 vs 건수에 비례"라는 차이는 유지됩니다.)

재현 방법(표준 라이브러리만 사용):

```python
# bench.py — 저장소 루트에서: python3 bench.py
import json, os, tempfile, tracemalloc
from budget_app.storage import TransactionRepository

path = os.path.join(tempfile.mkdtemp(), "transactions.jsonl")
with open(path, "w", encoding="utf-8") as f:
    for i in range(1, 100_001):
        f.write(json.dumps({"id": f"TX-{i:06d}", "type": "expense", "date": "2026-01-01",
                            "amount": 1000, "category": "food", "memo": f"m{i}", "tags": []}) + "\n")
repo = TransactionRepository(path)
for name, fn in (("generator", lambda: sum(1 for _ in repo.iter_all())),
                 ("list", lambda: len(list(repo.iter_all())))):
    tracemalloc.start(); fn(); peak = tracemalloc.get_traced_memory()[1]; tracemalloc.stop()
    print(f"{name:10s} 최대 메모리 {peak / 1e6:.2f} MB")
```

한계도 있습니다. `search`는 **조건에 맞는 결과**를 정렬하려고 리스트에 모으므로, 거의 모든 거래가 조건에 맞으면 결과 크기만큼 메모리를 씁니다. 파일 전체를 올리는 것보다는 작지만 "상수"는 아닙니다.

### 6-2. 데코레이터로 공통 기능 분리

**무엇인가** — `decorators.py`의 `track` 하나가 **모든 명령 함수(`cmd_*` 16개)** 에 `@track`으로 붙어 세 가지 공통 기능을 처리합니다.

| 기능 | 하는 일 |
| --- | --- |
| 실행 로그 | 시작/완료/오류를 `app.log`에 기록 (`[시작] cmd_add`, `[완료] cmd_add (0.003초)`) |
| 실행 시간 측정 | `time.perf_counter()`로 소요 시간을 재서 로그에 남김 |
| 예외 처리 + 종료 코드 | `AppError`는 `[오류] 원인`/`[힌트] 해결 방법`으로, 예상 못 한 예외도 스택트레이스 없이 `[오류] 예상치 못한 문제가 발생했습니다`로 **표준 에러(stderr)** 에 출력. 성공이면 `0`, 실패면 `1`을 반환 |

**왜 분리가 필요했나**

1. **중복 제거**: 분리하지 않으면 16개 함수마다 `try/except`, 로그, 시간 측정 코드가 똑같이 반복됩니다. 하나를 고치면 15개를 같이 고쳐야 하고, 하나라도 빠지면 어떤 명령만 오류 문구가 다르거나 종료 코드가 0이 되는 버그가 생깁니다.
2. **업무 흐름에 집중**: `cmd_*` 함수에는 "입력 받기 → 서비스 호출 → 결과 출력"만 남습니다.
3. **일관성의 단일 지점**: 오류 문구 형식(`[오류]`/`[힌트]`)과 종료 코드 규칙이 `track` 한 곳에만 있습니다.
4. 세 가지를 한 데코레이터로 묶은 이유는 모두 "명령 하나의 시작~끝"이라는 같은 생명주기를 공유하기 때문입니다(시작 시점에 로그를 남기고, 같은 구간의 시간을 재고, 같은 구간에서 난 예외를 잡음).

```python
@track
def cmd_delete(args: argparse.Namespace, services: Services) -> None:
    tx_service, *_ = services
    tx_service.delete(args.tid)          # 없는 id면 NotFoundError가 올라옴
    print(f"[삭제 완료] id={args.tid}")
# → track이 NotFoundError를 잡아 "[오류] ..."/"[힌트] ..."를 출력하고 1을 반환
```

### 6-3. 타입 힌트

**적용 범위** — 모든 공개 함수/메서드에 매개변수와 반환 타입을 붙였습니다. CLI의 `cmd_*`는 모두 `(args: argparse.Namespace, services: Services) -> None`으로 통일했고, `Services`는 서비스 4종 튜플의 타입 별칭(`Tuple[TransactionService, CategoryService, BudgetService, SummaryService]`)입니다.

**실제 코드로 이점을 확인한 방법** — 같은 함수를 예로 세 단계로 확인했습니다.

① **함수 계약이 코드에서 바로 읽힌다** (표준 라이브러리 `inspect`/`typing`으로 확인 가능)

```python
>>> import inspect, typing
>>> from budget_app.services import TransactionService
>>> inspect.signature(TransactionService.list_recent)
(self, limit: int = 10) -> List[budget_app.models.Transaction]
>>> typing.get_type_hints(TransactionService.list_recent)
{'limit': <class 'int'>, 'return': typing.List[budget_app.models.Transaction]}
```

`list_recent`가 "정수 개수를 받아 `Transaction` 리스트를 돌려준다"는 사실을 구현을 읽지 않고도 알 수 있습니다.

② **실행 전에 잘못된 사용을 잡는다** — 타입 힌트는 실행 시점에는 강제되지 않습니다. 일부러 틀린 호출을 하면 실행해야만 오류가 납니다.

```python
svc.list_recent(limit="10")
# 실행 결과: TypeError: '<=' not supported between instances of 'str' and 'int'
```

타입 검사기(`mypy`)를 쓰면 **실행하기 전에** 같은 실수가 잡힙니다. (아래는 이 검증을 위해 따로 만든 연습용 파일 `demo_wrong.py`의 결과입니다.)

```
demo_wrong.py:4: error: Argument "limit" to "list_recent" of "TransactionService" has incompatible type "str"; expected "int"
demo_wrong.py:6: error: "int" has no attribute "upper"        # txs[0].amount 는 int
```

③ **리팩터링 중 실제로 잡힌 문제** — `TransactionService.update()`가 "값이 None이면 기존 값 유지"를 `a if a is not None else b` 형태로 6번 반복했는데, `mypy`가 이 부분에서 타입 오류 9개를 냈습니다(`Any | str | None`을 `str` 자리에 넣을 수 없음). 런타임 오류는 아니었지만 "None이 섞일 수 있다"는 신호였기 때문에, `_pick(new: Optional[T], current: T) -> T` 헬퍼 하나로 바꿨고 `mypy budget_app` 결과가 **오류 0개**(`Success: no issues found in 9 source files`)가 됐습니다.

> `mypy`는 **개발 중 검증 도구일 뿐 프로그램의 의존성이 아닙니다.** 프로그램 실행·테스트에는 필요 없고(`pip install mypy`를 하지 않아도 모든 기능이 동작), 위 ①은 표준 라이브러리만으로 확인됩니다.

---

## 7. 저장 포맷과 확장성

### 7-1. JSONL vs CSV — 왜 JSONL인가

내부 저장은 **JSONL**, 외부와 주고받는 교환 포맷은 **CSV(import/export)** 로 용도를 나눴습니다.

| 비교 항목 | JSONL | CSV |
| --- | --- | --- |
| 한 줄 = 레코드 하나 (append-only, 스트리밍에 유리) | O | O |
| 리스트 필드(`tags`) 표현 | 네이티브 (`["meal","cafe"]`) | 쉼표가 컬럼 구분자와 충돌 → 따옴표 규칙 필요 |
| `memo`에 쉼표·따옴표·줄바꿈이 섞여도 | JSON 이스케이프가 표준으로 처리 | 인용부호 규칙을 직접 신경 써야 함 |
| 타입 보존 (정수 vs 문자열) | O | X (전부 문자열) |
| 필드 추가 시 하위 호환 | 쉬움 (없는 키는 `.get()` 기본값) | 헤더·컬럼 순서가 바뀌면 파서 전체 영향 |
| 스프레드시트에서 바로 열기 | X | O |
| 사람이 눈으로 훑어보기 | 보통 (JSON 한 줄) | 쉬움 |

**근거**: 이 앱의 데이터에는 리스트 타입(`tags`)과 자유 입력 문자열(`memo`)이 있어서, 이스케이프를 직접 관리하지 않아도 안전한 JSONL이 더 적합합니다. 반대로 `import/export`는 "스프레드시트에서 편집해서 주고받는" 상황이 목적이므로 보편적인 CSV가 맞습니다. **단점도 알고 선택했습니다**: JSONL은 엑셀로 바로 열 수 없고, 중간 한 줄만 수정하는 것이 안 되어(전체 재작성) 수정/삭제가 O(n)입니다.

### 7-2. 거래가 10만 건이 되면

가상의 숫자가 아니라 거래 100,000건짜리 파일(`transactions.jsonl`)을 만들어 명령 하나를 실행하는 **전체 시간**을 쟀습니다(프로세스 시작 포함, Python 3.13, 1회 측정).

| 명령 | 시간 | 비고 |
| --- | --- | --- |
| `list --limit 10` | 0.26초 | `nlargest`로 최신 10개만 유지 |
| `search --category food --from … --to …` (한 달) | 0.33초 | 전체 훑기 + 결과만 정렬 |
| `summary --month 2026-03` | 0.26초 | 전체 훑으면서 누적 |
| `export --month 2026-03` | 0.42초 | |
| `add` (1건) | 0.34초 | 마지막 id를 알기 위해 파일을 1회 훑음 |
| `update --id …` | **0.80초** | 전체 재작성 |
| `delete --id …` | **0.95초** | 전체 재작성 |

**병목은 어디인가** — 조회 계열은 "한 번 훑기(O(n))"이고 아직 견딜 만합니다. 가장 먼저 느려지는 곳은 **수정/삭제**입니다. 1건을 고치려고 10만 줄을 모두 다시 쓰기 때문이고(위 표에서 조회의 약 3배), 건수가 늘수록 선형으로 느려집니다.

**어떻게 개선할까**

| 병목 | 현재 상태 | 개선 방법 |
| --- | --- | --- |
| ① `next_id()`가 `add`마다 파일 전체를 재스캔 → `import` 시 O(n²) | **해결함**: 프로세스 안에서 최초 1회만 스캔하고 이후 메모리에서 +1 (`_next_seq`). 3,000건 add: 약 12.8초(개선 전 방식을 그대로 재현해 측정) → 0.16초, 5,000행 CSV import: 0.24초 | — |
| ② `update`/`delete` 전체 재작성 | 미구현(제안) | id → byte offset 인덱스 파일을 두고 해당 줄만 갱신하거나, 표준 라이브러리 `sqlite3`로 전환해 인덱스 기반 갱신 (미션 제약상 "JSONL/CSV 중 1개"를 벗어나는 큰 변경이라 제안으로만 둠) |
| ③ `list`가 전체 정렬 | **해결함**: `nlargest`로 최신 N개만 유지(O(n log N)). 추가 개선: 파일을 뒤에서부터 읽어 N개만 확보하면 O(N) | 역방향 읽기 / `deque(maxlen=N)` |
| ④ `summary`가 월과 무관하게 전체를 읽음 | 미구현(제안) | 월별 파일 분리(`2026-03.jsonl`) 또는 월 인덱스. 단 "파일 3개" 제약과 충돌하므로 제안으로만 둠 |

병렬 처리(멀티프로세싱)는 선택하지 않았습니다. 병목이 CPU 계산이 아니라 **디스크 순차 읽기**여서, 코어를 늘리기보다 읽는 양을 줄이는 쪽(인덱싱·파티셔닝)이 근본 해결책이라고 판단했습니다.

### 7-3. import CSV에 깨진 행이 섞이면

**선택한 방식: 부분 성공 + 건너뛴 행 리포트**

1. **파일 전체 단위 문제**(파일 없음, 필수 헤더 누락)는 아무것도 저장하지 않고 즉시 거부합니다. 어떤 헤더가 빠졌는지 알려줍니다.
2. **행 단위 문제**(날짜 형식 오류, 없는 카테고리, 숫자가 아닌 금액 등)는 그 행만 건너뛰고 나머지 정상 행은 저장합니다.
3. 끝에 `imported=N, skipped=M`으로 **건수를 보고**하고, 건너뛴 행은 `app.log`에 **줄 번호(헤더=1행)와 사유**를 남깁니다.

```bash
$ python3 -m budget_app import --from import.csv
[완료] imported=1, skipped=2
[안내] 건너뛴 행의 상세 사유는 app.log에서 확인할 수 있습니다.
$ grep 건너뜀 app.log
... WARNING [import 건너뜀] import.csv 3행: 날짜 형식이 올바르지 않습니다: 2026-13-01
... WARNING [import 건너뜀] import.csv 4행: 등록되지 않은 카테고리입니다: 여행
```

**왜 이 방식인가** (사용자 신뢰 관점)

| 방식 | 장점 | 단점 |
| --- | --- | --- |
| 전체 롤백 | 파일이 "전부 아니면 전혀"라 상태가 단순 | 5,000행 중 1행 오타 때문에 전체가 거부됨 → 사용자가 어느 행인지 찾아 고칠 때까지 아무것도 못 씀 |
| **부분 성공 + 리포트 (채택)** | 정상 데이터는 보존, 문제 행은 줄 번호로 찾을 수 있음 | 건너뛴 행을 고쳐 **다시 import할 때, 이미 들어간 정상 행까지 포함된 파일이면 중복 저장됨** |
| 무조건 무시 | 구현 쉬움 | 몇 행이 빠졌는지 모르면 데이터가 조용히 사라짐 → 신뢰 훼손 |

중요한 것은 "**조용히 사라지지 않는다**"는 점입니다. 건수를 반드시 보여주고, 사유를 줄 번호와 함께 남깁니다. 재import 시 중복을 피하려면 **건너뛴 행만 새 CSV로 만들어서** 다시 가져오세요.

개선 제안(미구현): `import --dry-run`(검증만 하고 저장하지 않음), `import --strict`(한 행이라도 오류면 전체 거부), 중복 거래 감지.

---

## 8. 보너스 과제

| 보너스 | 구현 | 배움 포인트 | 실행 |
| --- | --- | --- | --- |
| ① 백업 | `backup`이 `data/backup/<YYYYMMDD_HHMMSS>/`에 존재하는 데이터 파일을 복사 (최대 4개) | 파일 처리 + 운영 안전장치 | [2-11](#2-11-백업-backup-보너스) |
| ② 반복 내역 | `recurring add/list/apply`. 규칙이 `applied_months`를 기록해 같은 달 중복 생성 방지, 생성일은 1~28로 제한(2월에도 항상 존재) | 규칙 기반 데이터 생성 + 예외 처리 | [2-12](#2-12-반복-내역-recurring-보너스) |
| ③ 출력 포맷 정렬 | 외부 라이브러리 없이 `str.ljust/rjust`로 `list` 컬럼 정렬 | 콘솔 UX + 포맷터 분리 (`format_transaction`) | [2-3](#2-3-거래-목록-list) |
| ④ 저장 원자성 강화 | 임시 파일에 쓰고 `os.replace`로 교체, 실패 시 원본 유지 | 파일 기반 트랜잭션/원자성 | [5-3](#5-3-파일-기반-updatedelete를-안전하게-처리한-방법) |

**백업 복구 절차** (별도 명령 없이 수동 복원):

```bash
ls data/backup/                                              # 복구할 시점 확인
cp data/backup/20261107_213542/*.jsonl data/                 # 해당 시점 파일로 덮어쓰기
python3 -m budget_app list                                   # 정상 복구 확인
```

---

## 9. 프로젝트 구조

```
budget_app/
  __init__.py
  __main__.py     # python3 -m budget_app 진입점
  models.py       # Transaction, Category, Budget, RecurringRule
  exceptions.py   # AppError, ValidationError, NotFoundError
  decorators.py   # track (로그 / 시간 측정 / 예외 처리)
  utils.py        # 검증, 원자적 파일 쓰기, id 생성
  storage.py      # Repository 4종 (파일 I/O 전담)
  services.py     # Service 5종 (검증 + 업무 로직)
  cli.py          # argparse + cmd_* 핸들러
tests/
  test_services.py  # 서비스 단위 테스트 (23개)
  test_cli.py       # CLI 통합 테스트: 종료 코드, export/import, 재실행 유지 (10개)
data/               # 실행 시 자동 생성 (git 제외)
app.log             # 실행 로그 (자동 생성, git 제외)
```

주요 클래스: `TransactionService` · `CategoryService` · `BudgetService` · `SummaryService` · `RecurringService` / `TransactionRepository` · `CategoryRepository` · `BudgetRepository` · `RecurringRepository`.

---

## 10. 오류 처리와 종료 코드

- **스택트레이스 없이** `[오류] 원인` + `[힌트] 해결 방법`을 표준 에러(stderr)로 출력합니다. 모든 사용자 대상 오류는 `AppError(message, hint)` 하나의 형태로 만들고, 출력 문구 조립은 `track` 한 곳에서만 합니다.
- **종료 코드**

| 코드 | 의미 |
| --- | --- |
| `0` | 정상 종료 |
| `1` | 프로그램이 처리한 오류(잘못된 입력, 없는 id/파일, 손상된 데이터 파일 등) 및 예상 못 한 예외 |
| `2` | 명령행 사용법 오류(없는 명령/옵션, 필수 옵션 누락 등 — `argparse`) |

- 데이터 파일이 손상된 경우도 안내합니다.
  ```
  [오류] 저장 파일을 읽을 수 없습니다: ./data/transactions.jsonl
  [힌트] 데이터 파일이 손상되었을 수 있습니다. 백업 파일을 확인하세요.
  ```
- 자동 검증: `tests/test_cli.py`가 실제로 `python3 -m budget_app`을 실행해 종료 코드와 `Traceback` 미출력을 확인합니다.

---

## 11. 테스트

```bash
python3 -m unittest discover -s tests -t .      # 33개
```

각 테스트는 임시 폴더를 사용하므로 실제 `./data`, `app.log`를 건드리지 않습니다.

- `test_services.py` (23개): 입력 검증, id 발급, 없는 id의 update/delete, 카테고리 중복/사용 중 삭제 차단, `--replace-with` 이관, 예산 사용률·초과 경고, 월별 TOP N, 반복 내역 중복 방지
- `test_cli.py` (10개): 성공/오류 종료 코드와 스택트레이스 미출력, 2월·4월 `export --month`, import 부분 성공·헤더 누락·BOM·파일 없음, 재실행 후 데이터 유지

---

## 12. 알려진 한계

- 두 프로세스가 동시에 같은 데이터 폴더에 쓰는 경우를 막는 잠금이 없습니다(개인용 단일 사용 가정).
- 원자적 교체는 하지만 `fsync`는 하지 않아, 정전 직후의 내용까지 보장하지는 않습니다.
- `import`를 같은 파일로 두 번 실행하면 거래가 중복 저장됩니다(중복 감지 없음).
- `Ctrl+C`로 중단하면 파이썬 기본 중단 메시지가 출력됩니다(잘못된 입력 처리와는 별개).
- 10만 건 이상에서 `update`/`delete`는 전체 재작성이라 건수에 비례해 느려집니다([7-2](#7-2-거래가-10만-건이-되면)).

## 13. 개발 환경 / 제약

- Python 3.10 이상, **표준 라이브러리만 사용** (외부 패키지 설치 불필요 — 테스트도 `unittest`만 사용)
- 옵션 표기는 `--`(예: `--limit`, `--from`, `--month`)로 통일
- 저장은 JSONL 3개 이상 파일(`transactions`/`categories`/`budgets`) 분리
