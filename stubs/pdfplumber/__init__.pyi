from pathlib import Path
from types import TracebackType

class Page:
    page_number: int
    def extract_text(self) -> str | None: ...

class PDF:
    pages: list[Page]
    def __enter__(self) -> PDF: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...
    def close(self) -> None: ...

def open(path_or_fp: str | Path) -> PDF: ...
