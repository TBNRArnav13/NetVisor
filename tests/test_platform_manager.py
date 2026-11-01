import unittest
from unittest.mock import patch, MagicMock
import sys
import os

from netcap_common.platform_manager import PlatformManager


class TestPlatformManager(unittest.TestCase):
    """Test suite for PlatformManager."""

    def setUp(self):
        self.pm = PlatformManager()

    def test_detect_platform(self):
        platform = self.pm.detect_platform()
        self.assertIn(platform, ["Windows", "Linux", "Darwin", "Unknown"])

    def test_check_dependencies(self):
        results = self.pm.check_dependencies()
        self.assertIn('platform', results)
        self.assertIn('privileges', results)
        self.assertIn('tshark', results)
        self.assertIn('python', results)
        self.assertEqual(results['python']['status'], 'ok')

    def test_check_privileges(self):
        has_priv = self.pm.check_privileges()
        self.assertIsInstance(has_priv, bool)

    def test_get_dependency_report(self):
        report = self.pm.get_dependency_report()
        self.assertIsInstance(report, str)
        self.assertIn("Dependency Status Report", report)


if __name__ == '__main__':
    unittest.main()
