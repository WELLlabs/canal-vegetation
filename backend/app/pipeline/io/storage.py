"""Storage backends. Pipeline code talks to StorageBackend only."""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import Settings, get_settings


class StorageBackend(ABC):
    @abstractmethod
    def save_file(self, src: Path | str, dest_key: str) -> str:
        """Copy a local file to storage. Returns a path/URI the pipeline can open later."""

    @abstractmethod
    def save_bytes(self, data: bytes, dest_key: str) -> str:
        pass

    @abstractmethod
    def local_path(self, key_or_path: str) -> str:
        """Return a filesystem path Rasterio/OpenCV can open (download if remote)."""

    @abstractmethod
    def public_url(self, key_or_path: str) -> str:
        """Frontend-facing relative or absolute URL."""

    def exists(self, key_or_path: str) -> bool:
        if key_or_path.startswith("s3://"):
            return True
        return Path(key_or_path).is_file()


class LocalStorage(StorageBackend):
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save_file(self, src: Path | str, dest_key: str) -> str:
        dest = self.root / dest_key
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return str(dest.resolve())

    def save_bytes(self, data: bytes, dest_key: str) -> str:
        dest = self.root / dest_key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return str(dest.resolve())

    def local_path(self, key_or_path: str) -> str:
        p = Path(key_or_path)
        if p.is_file():
            return str(p.resolve())
        candidate = self.root / key_or_path
        return str(candidate.resolve())

    def public_url(self, key_or_path: str) -> str:
        p = Path(key_or_path)
        try:
            rel = p.resolve().relative_to(self.root.resolve())
            return f"/api/v1/files/{rel.as_posix()}"
        except ValueError:
            return f"/api/v1/files/{p.name}"


class S3Storage(StorageBackend):
    def __init__(
        self,
        bucket: str,
        prefix: str,
        region: str,
        cache_dir: Path,
        access_key_id: str = "",
        secret_access_key: str = "",
    ) -> None:
        if not bucket:
            raise ValueError("S3_BUCKET is required when STORAGE_BACKEND=s3")
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.region = region
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _client(self):
        import boto3

        kwargs: dict = {"region_name": self.region}
        if self.access_key_id and self.secret_access_key:
            kwargs["aws_access_key_id"] = self.access_key_id
            kwargs["aws_secret_access_key"] = self.secret_access_key
        return boto3.client("s3", **kwargs)

    def _s3_key(self, dest_key: str) -> str:
        dest_key = dest_key.replace("\\", "/").lstrip("/")
        if self.prefix:
            return f"{self.prefix}/{dest_key}"
        return dest_key

    def save_file(self, src: Path | str, dest_key: str) -> str:
        key = self._s3_key(dest_key)
        self._client().upload_file(str(src), self.bucket, key)
        return f"s3://{self.bucket}/{key}"

    def save_bytes(self, data: bytes, dest_key: str) -> str:
        key = self._s3_key(dest_key)
        self._client().put_object(Bucket=self.bucket, Key=key, Body=data)
        return f"s3://{self.bucket}/{key}"

    def exists(self, key_or_path: str) -> bool:
        if key_or_path.startswith("s3://"):
            _, _, rest = key_or_path.partition("s3://")
            bucket, _, key = rest.partition("/")
            try:
                self._client().head_object(Bucket=bucket, Key=key)
                return True
            except Exception:
                return False
        return Path(key_or_path).is_file()

    def local_path(self, key_or_path: str) -> str:
        if key_or_path.startswith("s3://"):
            _, _, rest = key_or_path.partition("s3://")
            bucket, _, key = rest.partition("/")
            dest = self.cache_dir / Path(key).name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                self._client().download_file(bucket, key, str(dest))
            return str(dest)
        return str(Path(key_or_path).resolve())

    def public_url(self, key_or_path: str) -> str:
        if key_or_path.startswith("s3://"):
            _, _, rest = key_or_path.partition("s3://")
            bucket, _, key = rest.partition("/")
            return f"https://{bucket}.s3.{self.region}.amazonaws.com/{key}"
        return key_or_path


def get_storage(settings: Settings | None = None) -> StorageBackend:
    settings = settings or get_settings()
    if settings.storage_backend.lower() == "s3":
        return S3Storage(
            bucket=settings.s3_bucket,
            prefix=settings.s3_prefix,
            region=settings.s3_region,
            cache_dir=settings.data_dir / "s3_cache",
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
        )
    return LocalStorage(settings.output_dir)
