# 나만의 용돈 기입장 (codyssey-B2-1)

Python 표준 라이브러리만으로 만든 파일 기반 콘솔 가계부입니다.
거래 추가/조회/검색/수정/삭제, 월별 요약, 카테고리·예산 관리, CSV 가져오기/내보내기를 지원합니다.

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

데이터 저장 폴더는 기본값 `./data`이며, `--data-dir` 옵션으로 변경할 수 있습니다.

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
data/                      # 실행 시 자동 생성 (저장 파일)
  transactions.jsonl
  categories.jsonl
  budgets.jsonl
app.log                     # 실행 로그 (자동 생성)
```

## 아키텍처

4개 계층으로 책임을 분리했습니다.

- **CLI (cli.py)**: 사용자 입력(대화형 input / 옵션 인자)을 받아 서비스 계층을 호출하고 결과를 출력. `argparse`로 명령/옵션 구조를 정의.
- **Service (services.py)**: 입력 검증과 비즈니스 로직 담당. `CategoryService`, `TransactionService`, `BudgetService`, `SummaryService`로 책임을 나눔. CLI는 이 계층만 알고, 저장 방식(파일 포맷 등)은 몰라도 됨.
- **Repository (storage.py)**: 실제 파일 읽기/쓰기만 담당. 조회는 **제너레이터(yield)로 한 줄씩** 읽어 파일 전체를 메모리에 올리지 않음 — 저장 파일이 커져도 `list`/`search`/`summary`가 메모리 부담 없이 동작하는 이유.
- **Model (models.py)**: `dataclass`로 거래/카테고리/예산의 필드와 타입을 명확히 계약. `to_dict`/`from_dict`로 JSONL 직렬화를 캡슐화.

**데코레이터**: `decorators.py`의 `track`이 모든 CLI 명령 함수(`cmd_*`)에 적용되어, 1) 실행 로그(`app.log`), 2) 실행 시간 측정, 3) 예외를 스택트레이스 없이 `[오류] 원인` + `[힌트] 해결법`으로 변환하는 세 가지를 한 번에 처리합니다.

## 저장 방식

- 포맷: **JSONL** (한 줄에 JSON 객체 하나)
- 위치: `./data` (`--data-dir`로 변경 가능), 파일 3개로 분리 저장
  - `transactions.jsonl` — 거래 내역
  - `categories.jsonl` — 카테고리 목록
  - `budgets.jsonl` — 월별 예산
- 최초 실행 시 `data/` 폴더와 파일이 자동 생성되고, 카테고리가 비어있으면 기본 카테고리(`food`, `transport`, `rent`, `etc`)가 자동으로 만들어집니다.
- `update`/`delete`는 전체 데이터를 임시 파일에 다시 쓴 뒤 `os.replace`로 원자적으로 교체합니다. 저장 도중 프로그램이 중단되어도 원본 파일이 손상되지 않습니다.

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

# 수정 / 삭제
$ python -m budget_app update --id TX-000001 --amount 18000 --memo 점심수정
$ python -m budget_app delete --id TX-000001

# CSV 내보내기 / 가져오기
$ python -m budget_app export --out export.csv --month 2024-01
$ python -m budget_app import --from import.csv
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

인코딩은 UTF-8, 첫 줄은 헤더입니다. `export`는 `--month YYYY-MM` 또는 `--from/--to` 중 하나 이상의 조건이 필수입니다. `import`는 형식에 맞지 않거나 등록되지 않은 카테고리인 행은 건너뛰고, 처리 결과를 `imported=N, skipped=M`으로 출력합니다.

## 오류 처리

- 잘못된 입력(날짜 형식, 0 이하 금액, 존재하지 않는 카테고리/id 등)은 파이썬 스택트레이스 대신 `[오류] 원인` + `[힌트] 해결 방법` 형태로 출력합니다.
- 정상 종료는 exit code 0, 오류 종료는 1입니다.
- 모든 명령의 실행 로그(시작/완료/오류, 소요 시간)는 `app.log`에 기록됩니다.

## 개발 환경 / 제약

- Python 3.10 이상, 표준 라이브러리만 사용 (외부 패키지 설치 불필요)
- 옵션 표기는 `--`(예: `--limit`, `--from`, `--month`)로 통일