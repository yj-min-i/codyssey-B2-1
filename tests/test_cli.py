"""CLI 통합 테스트 (표준 라이브러리 unittest + subprocess만 사용).

실제로 `python3 -m budget_app ...` 를 별도 프로세스로 실행해서
출력 문구와 종료 코드(0 / 0이 아님)를 확인한다.
각 테스트는 임시 폴더를 작업 폴더로 쓰므로 실제 ./data, app.log를 건드리지 않는다.

실행 방법(저장소 루트에서):
    python3 -m unittest discover -s tests -t .
"""
import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class CliTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, stdin=""):
        env = dict(os.environ, PYTHONPATH=REPO_ROOT)
        return subprocess.run(
            [sys.executable, "-m", "budget_app", *args],
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=self.cwd,
            env=env,
        )

    def add_tx(self, date, type_="expense", category="food", amount="1000", memo="", tags=""):
        proc = self.run_cli("add", stdin=f"{date}\n{type_}\n{category}\n{amount}\n{memo}\n{tags}\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc


class ExitCodeTests(CliTestCase):
    def test_success_returns_zero(self):
        proc = self.run_cli("category", "list")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("food", proc.stdout)

    def test_error_returns_nonzero_without_traceback(self):
        proc = self.run_cli("delete", "--id", "TX-999999")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("[오류]", proc.stderr)
        self.assertIn("[힌트]", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_invalid_date_input_returns_nonzero(self):
        proc = self.run_cli("add", stdin="2024-13-40\nexpense\nfood\n1000\n\n\n")
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn("Traceback", proc.stderr)


class ExportTests(CliTestCase):
    def test_export_month_with_30_or_28_days(self):
        """2월(28일), 4월(30일)처럼 31일이 없는 달도 --month 로 내보낼 수 있어야 한다."""
        self.add_tx("2026-02-28", memo="2월 말일")
        self.add_tx("2026-04-30", memo="4월 말일")
        for month, memo in (("2026-02", "2월 말일"), ("2026-04", "4월 말일")):
            out = os.path.join(self.cwd, f"{month}.csv")
            proc = self.run_cli("export", "--out", out, "--month", month)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("1 records", proc.stdout)
            with open(out, encoding="utf-8") as f:
                content = f.read()
            self.assertTrue(content.startswith("date,type,category,amount,memo,tags"))
            self.assertIn(memo, content)

    def test_export_without_condition_fails(self):
        proc = self.run_cli("export", "--out", os.path.join(self.cwd, "x.csv"))
        self.assertNotEqual(proc.returncode, 0)


class ImportTests(CliTestCase):
    def write_csv(self, text, encoding="utf-8"):
        path = os.path.join(self.cwd, "in.csv")
        with open(path, "w", encoding=encoding, newline="") as f:
            f.write(text)
        return path

    def test_partial_success_skips_bad_rows_and_logs_reason(self):
        path = self.write_csv(
            "date,type,category,amount,memo,tags\n"
            "2026-04-12,expense,food,4000,김밥,meal\n"
            "2024-13-40,expense,food,1000,잘못된날짜,\n"
            "2026-04-15,income,etc,7000,용돈,gift\n"
        )
        proc = self.run_cli("import", "--from", path)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("imported=2, skipped=1", proc.stdout)
        with open(os.path.join(self.cwd, "app.log"), encoding="utf-8") as f:
            self.assertIn("in.csv 3행", f.read())

    def test_missing_header_fails_with_hint(self):
        path = self.write_csv("date,type\n2026-04-01,expense\n")
        proc = self.run_cli("import", "--from", path)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("[힌트]", proc.stderr)

    def test_utf8_bom_file_is_accepted(self):
        path = self.write_csv(
            "date,type,category,amount,memo,tags\n2026-04-11,expense,food,3000,커피,cafe\n",
            encoding="utf-8-sig",
        )
        proc = self.run_cli("import", "--from", path)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("imported=1, skipped=0", proc.stdout)

    def test_missing_file_fails(self):
        proc = self.run_cli("import", "--from", os.path.join(self.cwd, "nope.csv"))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("[오류]", proc.stderr)


class PersistenceTests(CliTestCase):
    def test_data_survives_restart_in_three_files(self):
        self.add_tx("2026-04-10", memo="점심")
        self.assertEqual(self.run_cli("budget", "set", "--month", "2026-04", "--amount", "500000").returncode, 0)
        self.assertEqual(self.run_cli("category", "add", stdin="study\n").returncode, 0)

        # 새 프로세스(=재실행)에서 다시 읽어도 남아 있어야 한다.
        self.assertIn("점심", self.run_cli("list").stdout)
        self.assertIn("study", self.run_cli("category", "list").stdout)
        self.assertIn("500000원", self.run_cli("summary", "--month", "2026-04").stdout)

        for name in ("transactions.jsonl", "categories.jsonl", "budgets.jsonl"):
            self.assertTrue(os.path.getsize(os.path.join(self.cwd, "data", name)) > 0, name)


if __name__ == "__main__":
    unittest.main()
