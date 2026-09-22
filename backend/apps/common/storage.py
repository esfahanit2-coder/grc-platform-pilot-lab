from dataclasses import dataclass
from typing import BinaryIO

import boto3
from django.conf import settings


class ObjectStorage:
    def put(self, key: str, fileobj: BinaryIO, content_type: str | None = None) -> None:
        raise NotImplementedError

    def open_read(self, key: str) -> BinaryIO:
        raise NotImplementedError

    def presigned_get(self, key: str, expires: int = 300) -> str:
        raise NotImplementedError


@dataclass
class S3ObjectStorage(ObjectStorage):
    bucket: str = settings.S3_BUCKET

    def _client(self):
        return boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            aws_access_key_id=settings.S3_ACCESS_KEY or None,
            aws_secret_access_key=settings.S3_SECRET_KEY or None,
            region_name=settings.S3_REGION,
            use_ssl=settings.S3_USE_SSL,
        )

    def put(self, key: str, fileobj: BinaryIO, content_type: str | None = None) -> None:
        extra = {"ContentType": content_type} if content_type else {}
        self._client().upload_fileobj(fileobj, self.bucket, key, ExtraArgs=extra)

    def open_read(self, key: str) -> BinaryIO:
        # boto3 StreamingBody implements read()/close() and lets security
        # integrations inspect large Evidence objects without writing them to
        # the local filesystem or loading the whole object into application RAM.
        return self._client().get_object(Bucket=self.bucket, Key=key)["Body"]

    def presigned_get(self, key: str, expires: int = 300) -> str:
        return self._client().generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires,
        )
