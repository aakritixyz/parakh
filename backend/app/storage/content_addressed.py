import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import BinaryIO

from app.core.config import get_settings


class StoredBlob:
    def __init__(self, sha256: str, md5: str, size_bytes: int, path: Path) -> None:
        self.sha256 = sha256
        self.md5 = md5
        self.size_bytes = size_bytes
        self.path = path


class ContentAddressedStorage:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or get_settings().storage_root
        self.root.mkdir(parents=True, exist_ok=True)

    def put_fileobj(self, fileobj: BinaryIO, max_bytes: int | None = None) -> StoredBlob:
        sha256 = hashlib.sha256()
        md5 = hashlib.md5()  # noqa: S324 - recorded for legacy forensic compatibility only.
        size = 0
        temp_path = self.root / ".incoming"
        temp_path.mkdir(exist_ok=True)
        descriptor, raw_path = tempfile.mkstemp(prefix="seal-", dir=temp_path)
        work_path = Path(raw_path)
        with os.fdopen(descriptor, "wb") as out:
            while chunk := fileobj.read(1024 * 1024):
                size += len(chunk)
                if max_bytes is not None and size > max_bytes:
                    out.close()
                    work_path.unlink(missing_ok=True)
                    raise ValueError(f"File exceeds the {max_bytes}-byte upload limit")
                sha256.update(chunk)
                md5.update(chunk)
                out.write(chunk)
        digest = sha256.hexdigest()
        final = self.root / digest[:2] / digest[2:4] / digest
        final.parent.mkdir(parents=True, exist_ok=True)
        if final.exists():
            work_path.unlink()
        else:
            shutil.move(str(work_path), final)
            final.chmod(0o444)
        return StoredBlob(digest, md5.hexdigest(), size, final)

    def verify(self, path: str | Path, expected_sha256: str) -> bool:
        actual = hashlib.sha256()
        try:
            with Path(path).open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    actual.update(chunk)
        except OSError:
            return False
        return actual.hexdigest() == expected_sha256
