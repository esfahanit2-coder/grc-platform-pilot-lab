import io
import json
import tempfile
import zipfile
from pathlib import Path

from django.core.management.base import CommandError
from django.test import SimpleTestCase

from apps.common.management.commands.pilot_objectstore_archive import Command


class FakeS3Client:
    def __init__(self, objects=None):
        self.objects = dict(objects or {})
        self.content_types = {key: "application/octet-stream" for key in self.objects}
        self.metadata = {key: {} for key in self.objects}

    def list_objects_v2(self, Bucket, **kwargs):
        return {
            "IsTruncated": False,
            "Contents": [{"Key": key, "Size": len(value)} for key, value in sorted(self.objects.items())],
        }

    def get_object(self, Bucket, Key):
        return {
            "Body": io.BytesIO(self.objects[Key]),
            "ContentType": self.content_types.get(Key, "application/octet-stream"),
            "Metadata": self.metadata.get(Key, {}),
        }

    def upload_fileobj(self, fileobj, bucket, key, ExtraArgs=None):
        self.objects[key] = fileobj.read()
        extra = ExtraArgs or {}
        self.content_types[key] = extra.get("ContentType", "application/octet-stream")
        self.metadata[key] = extra.get("Metadata", {})

    def delete_objects(self, Bucket, Delete):
        for row in Delete.get("Objects") or []:
            self.objects.pop(row["Key"], None)


class PilotObjectStoreArchiveTests(SimpleTestCase):
    def test_export_and_replace_restore_round_trip(self):
        source = FakeS3Client(
            {
                "tenant/a/evidence/one.txt": b"alpha",
                "tenant/a/evidence/two.bin": b"\x00\x01\x02",
            }
        )
        source.content_types["tenant/a/evidence/one.txt"] = "text/plain"
        source.metadata["tenant/a/evidence/one.txt"] = {"classification": "internal"}

        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "objects.zip"
            Command()._export(source, "grc-evidence", archive_path)

            with zipfile.ZipFile(archive_path) as archive:
                manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["object_count"], 2)
            self.assertTrue(all(len(row["sha256"]) == 64 for row in manifest["objects"]))

            target = FakeS3Client({"stale-object": b"delete-me"})
            Command()._restore(target, "grc-evidence", archive_path, replace=True)
            self.assertEqual(target.objects, source.objects)
            self.assertEqual(target.content_types["tenant/a/evidence/one.txt"], "text/plain")
            self.assertEqual(
                target.metadata["tenant/a/evidence/one.txt"],
                {"classification": "internal"},
            )

    def test_restore_refuses_nonempty_bucket_without_replace(self):
        source = FakeS3Client({"one": b"1"})
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "objects.zip"
            Command()._export(source, "grc-evidence", archive_path)
            target = FakeS3Client({"existing": b"keep"})
            with self.assertRaisesMessage(CommandError, "not empty"):
                Command()._restore(target, "grc-evidence", archive_path, replace=False)
            self.assertEqual(target.objects, {"existing": b"keep"})
