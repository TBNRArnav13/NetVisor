import unittest
import tempfile
import shutil
from netcap_common.file_manager import FileManager


class TestFileManager(unittest.TestCase):
    """Test suite for FileManager."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.fm = FileManager(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_create_safe_filename(self):
        fname = self.fm.create_safe_filename("eth0", "pcap")
        self.assertTrue(fname.startswith("eth0_"))
        self.assertTrue(fname.endswith(".pcap"))

    def test_create_safe_filename_traversal(self):
        fname = self.fm.create_safe_filename("../../dangerous", "json")
        self.assertNotIn("..", fname)
        self.assertNotIn("/", fname)
        self.assertNotIn("\\", fname)


if __name__ == '__main__':
    unittest.main()
