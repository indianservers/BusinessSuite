import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("release_sites", Path(__file__).with_name("release_sites.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class RegistryTests(unittest.TestCase):
    def validate(self, items):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "deployment").mkdir()
            (root / "deployment/sites.json").write_text(json.dumps({"sites": items}))
            with patch.object(module, "ROOT", root):
                return module.sites()

    def test_registry_covers_both_customers_and_preserves_separate_configuration(self):
        items = module.sites()
        self.assertEqual(len(items), 4)
        portals = [item for item in items if item["kind"] == "interns-hub"]
        self.assertEqual(len({item["publicConfig"]["apiBaseUrl"] for item in portals}), 2)
        self.assertEqual(len({item["publicConfig"]["firebaseConfig"]["projectId"] for item in portals}), 2)

    def test_duplicate_project_cannot_receive_two_customer_configurations(self):
        item = copy.deepcopy(module.sites()[-1])
        second = copy.deepcopy(item)
        second["id"] = "another-customer"
        with self.assertRaises(ValueError): self.validate([item, second])

    def test_private_firebase_credentials_cannot_enter_release_configuration(self):
        item = copy.deepcopy(module.sites()[-1])
        item["publicConfig"]["firebaseConfig"]["private_key"] = "must-not-publish"
        with self.assertRaises(ValueError): self.validate([item])

    def test_credential_bearing_urls_are_rejected(self):
        item = copy.deepcopy(module.sites()[0])
        item["url"] = "https://user:password@example.com"
        with self.assertRaises(ValueError): self.validate([item])

if __name__ == "__main__": unittest.main()
