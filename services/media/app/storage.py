from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4


class LocalFileStorage:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def generate_key(self) -> str:
        value = uuid4().hex
        return f"{value[:2]}/{value[2:4]}/{value}"

    def _path_for(self, key: str) -> Path:
        path = (self.root / key).resolve()
        root = self.root.resolve()
        if root not in path.parents and path != root:
            raise ValueError("Invalid storage key")
        return path

    def write(self, key: str, content: bytes) -> None:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def read(self, key: str) -> Iterator[bytes]:
        with self._path_for(key).open("rb") as file:
            while chunk := file.read(1024 * 1024):
                yield chunk

    def delete(self, key: str) -> None:
        path = self._path_for(key)
        path.unlink(missing_ok=True)
        self._cleanup_empty_parents(path.parent)

    def _cleanup_empty_parents(self, path: Path) -> None:
        root = self.root.resolve()
        current = path.resolve()
        while current != root and root in current.parents:
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent
