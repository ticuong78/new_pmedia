import hashlib
from typing import Any, Optional

from diskcache import Cache


class DiskCache:
    """Disk-backed cache with deterministic key helper."""

    def __init__(self, directory: str = ".cache") -> None:
        self._cache = Cache(directory)

    @staticmethod
    def make_key(namespace: str, *parts: Any) -> str:
        rendered_parts = []
        for part in parts:
            if isinstance(part, bytes):
                rendered_parts.append(hashlib.sha256(part).hexdigest())
            else:
                rendered_parts.append(str(part))
        return f"{namespace}:" + ":".join(rendered_parts)

    def get(self, key: str) -> Optional[Any]:
        return self._cache.get(key)

    def set(self, key: str, value: Any, expire: Optional[int] = None) -> Any:
        self._cache.set(key, value, expire=expire)
        return value

    def delete(self, key: str) -> None:
        self._cache.delete(key)

    def clear(self) -> None:
        self._cache.clear()

    def close(self) -> None:
        self._cache.close()
