import json
import subprocess
import sys
import unittest
from pathlib import Path


class ServiceProtocolTests(unittest.TestCase):
    def test_single_request_is_replied_before_stdin_eof(self) -> None:
        request = json.dumps(
            {"id": "request-1", "method": "list_ssh_hosts", "params": {}},
            ensure_ascii=False,
        )
        result = subprocess.run(
            [sys.executable, "-u", "-m", "ssh_forwarder.service"],
            input=request + "\n",
            text=True,
            capture_output=True,
            cwd=Path(__file__).resolve().parents[1],
            timeout=10,
            check=True,
        )

        replies = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual(len(replies), 1)
        self.assertEqual(replies[0]["id"], "request-1")
        self.assertTrue(replies[0]["ok"])
        self.assertIsInstance(replies[0]["result"]["hosts"], list)

    def test_protocol_output_is_ascii_safe_for_windows_pipe_reader(self) -> None:
        request = json.dumps(
            {"id": "request-2", "method": "不存在的方法", "params": {}},
            ensure_ascii=False,
        )
        result = subprocess.run(
            [sys.executable, "-u", "-m", "ssh_forwarder.service"],
            input=request + "\n",
            text=True,
            capture_output=True,
            cwd=Path(__file__).resolve().parents[1],
            timeout=10,
            check=True,
        )

        self.assertTrue(all(ord(char) < 128 for char in result.stdout))
        reply = json.loads(result.stdout)
        self.assertFalse(reply["ok"])
        self.assertIn("未知服务方法", reply["error"])


if __name__ == "__main__":
    unittest.main()
