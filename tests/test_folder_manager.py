import unittest
import os
import shutil
import tempfile
from netcap_common.folder_manager import FolderManager


class TestFolderManager(unittest.TestCase):
    """Test suite for FolderManager."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.fm = FolderManager(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_directories_created(self):
        self.assertTrue(os.path.exists(self.fm.captures_dir))
        self.assertTrue(os.path.exists(self.fm.logs_dir))

    def test_cleanup_json(self):
        test_file = os.path.join(self.fm.captures_dir, "test_batch.json")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("{}")
        self.assertTrue(os.path.exists(test_file))
        self.fm.cleanup_json_files()
        self.assertFalse(os.path.exists(test_file))


if __name__ == '__main__':
    unittest.main()
