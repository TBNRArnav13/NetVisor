import unittest
from netcap_common.base_interfaces import CaptureConfig


class TestCaptureConfig(unittest.TestCase):
    """Test suite for CaptureConfig validation and properties."""

    def test_default_config(self):
        config = CaptureConfig(interface="eth0", output_directory=".")
        self.assertEqual(config.interface, "eth0")
        self.assertEqual(config.output_directory, ".")
        self.assertIsNone(config.duration)
        self.assertEqual(config.batch_interval, 5)

    def test_custom_config(self):
        config = CaptureConfig(
            interface="Wi-Fi",
            output_directory="./test",
            duration=30,
            batch_interval=10,
            json_logging=True
        )
        self.assertEqual(config.interface, "Wi-Fi")
        self.assertEqual(config.duration, 30)
        self.assertEqual(config.batch_interval, 10)
        self.assertTrue(config.json_logging)


if __name__ == '__main__':
    unittest.main()
