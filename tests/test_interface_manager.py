import unittest
from unittest.mock import patch, MagicMock
from netcap_common.interface_manager import InterfaceManager, InterfaceInfo
from netcap_common.platform_manager import PlatformManager


class TestInterfaceManager(unittest.TestCase):
    """Test suite for InterfaceManager."""

    def setUp(self):
        self.pm = PlatformManager()
        self.im = InterfaceManager(self.pm)

    def test_sanitize_interface_name(self):
        test_cases = [
            ("eth0", "eth0"),
            ("Wi-Fi", "Wi-Fi"),
            ("  interface  ", "interface"),
            (".interface.", "interface"),
            ("...", "unknown"),
            ("", "unknown"),
        ]
        for inp, expected in test_cases:
            self.assertEqual(self.im.sanitize_interface_name(inp), expected)

    def test_calculate_similarity(self):
        self.assertEqual(self.im._calculate_similarity("eth0", "eth0"), 1.0)
        self.assertEqual(self.im._calculate_similarity("", ""), 1.0)
        self.assertEqual(self.im._calculate_similarity("eth0", ""), 0.0)
        self.assertGreaterEqual(self.im._calculate_similarity("eth0", "eth1"), 0.5)

    def test_list_interfaces(self):
        interfaces = self.im.list_interfaces()
        self.assertIsInstance(interfaces, list)
        self.assertGreater(len(interfaces), 0)


if __name__ == '__main__':
    unittest.main()
