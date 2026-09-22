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


class PilotBackupScriptContractTests(SimpleTestCase):
    def test_backup_preserves_active_tls_and_local_ai_compose_overlays(self):
        root = Path(__file__).resolve().parents[3]
        script = (root / "scripts" / "pilot-backup.sh").read_text(encoding="utf-8")
        self.assertIn('if [[ "${PILOT_TLS:-NO}" == "YES" ]]', script)
        self.assertIn("COMPOSE+=(-f docker-compose.pilot.tls.yml)", script)
        self.assertIn('if [[ "${PILOT_LOCAL_AI:-NO}" == "YES" ]]', script)
        self.assertIn("COMPOSE+=(--profile local-ai)", script)


class PilotRestoreScriptContractTests(SimpleTestCase):
    def test_restore_migration_plan_preserves_host_operator_ownership(self):
        root = Path(__file__).resolve().parents[3]
        script = (root / "scripts" / "pilot-restore.sh").read_text(encoding="utf-8")
        self.assertIn('--user "$(id -u):$(id -g)"', script)
        self.assertIn("restore-migration-plan.json", script)

class PilotPostgresComposeContractTests(SimpleTestCase):
    def test_postgres18_uses_parent_persistent_volume_layout(self):
        root = Path(__file__).resolve().parents[3]
        compose = (root / "docker-compose.pilot.yml").read_text(encoding="utf-8")
        self.assertIn("pgvector/pgvector:0.8.6-pg18-trixie", compose)
        self.assertIn("postgres_pilot_data:/var/lib/postgresql", compose)
        self.assertNotIn("postgres_pilot_data:/var/lib/postgresql/data", compose)
