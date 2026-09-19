"""`python -m budget_app <command> [options]` 실행 진입점."""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())