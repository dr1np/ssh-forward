import json
import tempfile
import unittest
from pathlib import Path

from ssh_forwarder.models import ForwardProfile
from ssh_forwarder.storage import ProfileStore


class ProfileStoreTests(unittest.TestCase):
    def test_round_trip_and_update(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            store = ProfileStore(path)
            profile = ForwardProfile(
                name="API",
                ssh_host="gateway",
                local_port=9000,
                remote_host="api.internal",
                remote_port=443,
            )
            store.upsert(profile)
            profile.local_port = 9001
            store.upsert(profile)

            loaded = ProfileStore(path)
            loaded.load()
            self.assertEqual(len(loaded.favorites), 1)
            self.assertEqual(loaded.favorites[0].local_port, 9001)

            loaded.delete(profile.id)
            self.assertEqual(loaded.favorites, [])

    def test_invalid_json_has_helpful_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text("not-json", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "无法读取配置文件"):
                ProfileStore(path).load()

    def test_invalid_favorites_shape_does_not_escape_as_type_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(json.dumps({"favorites": None}), encoding="utf-8")
            store = ProfileStore(path)
            with self.assertRaisesRegex(ValueError, "无法读取配置文件"):
                store.load()
            self.assertTrue(store.load_failed)

    def test_invalid_favorite_items_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(
                json.dumps({"favorites": [None, "not-a-profile", {"name": "missing-fields"}]}),
                encoding="utf-8",
            )
            store = ProfileStore(path)
            store.load()
            self.assertEqual(store.favorites, [])

    def test_duplicate_favorite_ids_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            profile = ForwardProfile(
                name="API",
                ssh_host="gateway",
                local_port=9000,
                remote_host="api.internal",
                remote_port=443,
            )
            payload = {"favorites": [profile.to_dict(), profile.to_dict()]}
            path.write_text(json.dumps(payload), encoding="utf-8")

            store = ProfileStore(path)
            store.load()

            self.assertEqual(len(store.favorites), 1)


if __name__ == "__main__":
    unittest.main()
