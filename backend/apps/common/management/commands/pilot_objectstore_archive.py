import hashlib
import json
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import boto3
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


ARCHIVE_SCHEMA_VERSION = 1
CHUNK_SIZE = 1024 * 1024


def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL or None,
        aws_access_key_id=settings.S3_ACCESS_KEY or None,
        aws_secret_access_key=settings.S3_SECRET_KEY or None,
        region_name=settings.S3_REGION,
        use_ssl=settings.S3_USE_SSL,
    )


def list_objects(client, bucket):
    token = None
    while True:
        kwargs = {"Bucket": bucket}
        if token:
            kwargs["ContinuationToken"] = token
        response = client.list_objects_v2(**kwargs)
        for row in response.get("Contents") or []:
            yield row
        if not response.get("IsTruncated"):
            break
        token = response.get("NextContinuationToken")
        if not token:
            raise CommandError("Object-store listing was truncated without a continuation token.")


def delete_all_objects(client, bucket):
    batch = []
    for row in list_objects(client, bucket):
        batch.append({"Key": row["Key"]})
        if len(batch) == 1000:
            client.delete_objects(Bucket=bucket, Delete={"Objects": batch, "Quiet": True})
            batch = []
    if batch:
        client.delete_objects(Bucket=bucket, Delete={"Objects": batch, "Quiet": True})


class Command(BaseCommand):
    help = "Export or restore the configured S3-compatible pilot object store."

    def add_arguments(self, parser):
        parser.add_argument("operation", choices=["export", "restore"])
        parser.add_argument("--archive", required=True, help="Archive path inside the backend container.")
        parser.add_argument(
            "--replace",
            action="store_true",
            help="For restore only: delete existing objects before restoring the archive.",
        )

    def handle(self, *args, **options):
        path = Path(options["archive"])
        client = s3_client()
        bucket = settings.S3_BUCKET
        try:
            client.head_bucket(Bucket=bucket)
        except Exception as exc:
            raise CommandError(f"Cannot access object-storage bucket {bucket!r}: {exc}") from exc

        if options["operation"] == "export":
            self._export(client, bucket, path)
        else:
            self._restore(client, bucket, path, replace=options["replace"])

    def _export(self, client, bucket, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        objects = list(list_objects(client, bucket))
        manifest = {
            "schema_version": ARCHIVE_SCHEMA_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_bucket": bucket,
            "object_count": len(objects),
            "objects": [],
        }
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            for index, row in enumerate(objects):
                key = row["Key"]
                response = client.get_object(Bucket=bucket, Key=key)
                archive_name = f"objects/{index:08d}.bin"
                digest = hashlib.sha256()
                size = 0
                with archive.open(archive_name, "w", force_zip64=True) as destination:
                    body = response["Body"]
                    while True:
                        chunk = body.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        digest.update(chunk)
                        size += len(chunk)
                        destination.write(chunk)
                manifest["objects"].append(
                    {
                        "key": key,
                        "archive_name": archive_name,
                        "size": size,
                        "sha256": digest.hexdigest(),
                        "content_type": response.get("ContentType") or "application/octet-stream",
                        "metadata": response.get("Metadata") or {},
                    }
                )
            archive.writestr(
                "manifest.json",
                json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2),
            )
        self.stdout.write(self.style.SUCCESS(f"Exported {len(objects)} objects to {path}"))

    def _restore(self, client, bucket, path, *, replace):
        if not path.is_file():
            raise CommandError(f"Archive does not exist: {path}")
        existing = list(list_objects(client, bucket))
        if existing and not replace:
            raise CommandError(
                "Target object-storage bucket is not empty. Re-run with --replace only after explicit restore approval."
            )

        with zipfile.ZipFile(path, "r") as archive:
            try:
                manifest = json.loads(archive.read("manifest.json"))
            except (KeyError, json.JSONDecodeError) as exc:
                raise CommandError("Archive manifest is missing or invalid.") from exc
            if manifest.get("schema_version") != ARCHIVE_SCHEMA_VERSION:
                raise CommandError("Unsupported object-store archive schema version.")
            rows = manifest.get("objects")
            if not isinstance(rows, list):
                raise CommandError("Archive manifest object list is invalid.")

            if existing and replace:
                delete_all_objects(client, bucket)

            restored = 0
            for row in rows:
                key = row.get("key")
                archive_name = row.get("archive_name")
                expected_sha256 = row.get("sha256")
                if not key or not archive_name or not expected_sha256:
                    raise CommandError("Archive manifest contains an incomplete object entry.")
                try:
                    source = archive.open(archive_name, "r")
                except KeyError as exc:
                    raise CommandError(f"Archive member is missing: {archive_name}") from exc
                digest = hashlib.sha256()
                with source, tempfile.SpooledTemporaryFile(max_size=8 * CHUNK_SIZE) as staged:
                    while True:
                        chunk = source.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        digest.update(chunk)
                        staged.write(chunk)
                    if digest.hexdigest() != expected_sha256:
                        raise CommandError(f"Checksum mismatch for archived object {key!r}.")
                    staged.seek(0)
                    extra = {
                        "ContentType": row.get("content_type") or "application/octet-stream",
                        "Metadata": row.get("metadata") or {},
                    }
                    client.upload_fileobj(staged, bucket, key, ExtraArgs=extra)
                restored += 1

        self.stdout.write(self.style.SUCCESS(f"Restored {restored} objects into bucket {bucket}"))
