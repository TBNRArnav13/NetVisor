import unittest
import tempfile
import shutil
import os
import json
from netcap_common.logging_manager import LoggingManager, JSONFormatter, UTCFormatter


class TestLoggingManager(unittest.TestCase):
    """Test suite for LoggingManager and custom formatters."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.test_dir, "test.log")
        self.lm = LoggingManager(session_id="test_session")

    def tearDown(self):
        self.lm.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_setup_logging_text(self):
        self.lm.setup_logging(self.log_file, json_mode=False, console_output=False)
        self.lm.logger.info("Hello NetVisor Text")
        self.assertTrue(os.path.exists(self.log_file))
        with open(self.log_file, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("Hello NetVisor Text", content)

    def test_setup_logging_json(self):
        json_log = os.path.join(self.test_dir, "test.json.log")
        self.lm.setup_logging(json_log, json_mode=True, console_output=False)
        self.lm.logger.info("Hello NetVisor JSON")
        self.assertTrue(os.path.exists(json_log))
        with open(json_log, 'r', encoding='utf-8') as f:
            line = f.readline().strip()
            data = json.loads(line)
            self.assertEqual(data['message'], "Hello NetVisor JSON")
            self.assertEqual(data['session_id'], "test_session")


if __name__ == '__main__':
    unittest.main()
