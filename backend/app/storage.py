from typing import Protocol
import os


class StorageBackend(Protocol):
    async def upload(self, key: str, data: bytes) -> str:
        """Upload bytes, return storage URI."""
        ...

    async def download(self, key: str) -> bytes:
        """Download bytes by key."""
        ...

    async def signed_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a time-limited download URL."""
        ...

    async def delete(self, key: str) -> None:
        """Delete a stored object."""
        ...


class LocalStorage:
    """Dev storage: saves files to ./storage/ directory."""

    def __init__(self, base_dir: str = "./storage"):
        os.makedirs(base_dir, exist_ok=True)
        self.base_dir = base_dir

    async def upload(self, key: str, data: bytes) -> str:
        path = os.path.join(self.base_dir, key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return f"local://{key}"

    async def download(self, key: str) -> bytes:
        path = os.path.join(self.base_dir, key)
        with open(path, "rb") as f:
            return f.read()

    async def signed_url(self, key: str, expires_in: int = 3600) -> str:
        return f"http://localhost:8000/files/{key}"

    async def delete(self, key: str) -> None:
        path = os.path.join(self.base_dir, key)
        if os.path.exists(path):
            os.remove(path)


class S3Storage:
    """Production storage: uses boto3 to interact with S3."""

    def __init__(
        self,
        bucket: str,
        endpoint: str = None,
        access_key: str = None,
        secret_key: str = None,
    ):
        import boto3

        kwargs = {}
        if endpoint:
            kwargs["endpoint_url"] = endpoint
        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            **kwargs,
        )
        self.bucket = bucket

    async def upload(self, key: str, data: bytes) -> str:
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data)
        return f"s3://{self.bucket}/{key}"

    async def download(self, key: str) -> bytes:
        resp = self.s3.get_object(Bucket=self.bucket, Key=key)
        return resp["Body"].read()

    async def signed_url(self, key: str, expires_in: int = 3600) -> str:
        return self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    async def delete(self, key: str) -> None:
        self.s3.delete_object(Bucket=self.bucket, Key=key)


def get_storage(settings) -> StorageBackend:
    """Factory: returns LocalStorage or S3Storage based on config."""
    if settings.STORAGE_BACKEND == "local":
        return LocalStorage(settings.LOCAL_STORAGE_DIR)
    else:
        return S3Storage(
            settings.S3_BUCKET,
            settings.S3_ENDPOINT,
            settings.S3_ACCESS_KEY,
            settings.S3_SECRET_KEY,
        )
