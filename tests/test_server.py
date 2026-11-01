import unittest
import os
import json
import tempfile
import shutil

from server import transform_packet_for_frontend, find_json_files


class TestServerLogic(unittest.TestCase):
    """Test suite for server packet parsing and transformation logic."""

    def test_transform_packet_format(self):
        backend_packet = {
            "timestamp": "2026-11-01T10:00:00.000Z",
            "packet_number": 42,
            "length": 1420,
            "protocols": ["IP", "TCP", "HTTP"],
            "source": "192.168.1.50",
            "destination": "93.184.216.34",
            "source_port": "54321",
            "destination_port": "80",
            "info": "HTTP GET /index.html"
        }

        transformed = transform_packet_for_frontend(backend_packet)
        self.assertIsNotNone(transformed)
        self.assertEqual(transformed['source'], "192.168.1.50")
        self.assertEqual(transformed['destination'], "93.184.216.34")
        self.assertEqual(transformed['protocol'], "HTTP")
        self.assertEqual(transformed['length'], 1420)
        self.assertEqual(transformed['source_port'], "54321")
        self.assertEqual(transformed['dest_port'], "80")


if __name__ == '__main__':
    unittest.main()
