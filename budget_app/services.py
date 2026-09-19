"""서비스 계층: 입력 검증 + 비즈니스 로직을 담당한다.

CLI 계층은 이 서비스들만 호출하고, 서비스는 저장소(storage.py)만 호출한다.
"""
from typing import List, Optional, Set, Union

from .exceptions import NotFoundError, ValidationError
from .models import Category
from .storage import CategoryRepository

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