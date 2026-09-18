import json
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from datetime import datetime
from pathlib import Path

from ssh_forwarder.models import ActiveTunnel, ForwardProfile
from ssh_forwarder.service import BackendService


class ServiceProtocolTests(unittest.TestCase):
    def test_finished_tunnel_can_be_deleted_but_running_tunnel_cannot(self) -> None:
        profile = ForwardProfile(
            name="test",
            ssh_host="server",
            local_port=18080,
            remote_host="127.0.0.1",
            remote_port=80,
        )
        finished = ActiveTunnel("finished", profile, SimpleNamespace(poll=lambda: 0), ended_at=datetime.now())
        running = ActiveTunnel("running", profile, SimpleNamespace(poll=lambda: None))
        records = {"finished": finished, "running": running}
        manager = Mock()
        manager.get.side_effect = lambda tunnel_id: records.get(tunnel_id)
        manager.remove_finished.side_effect = lambda tunnel_id: records.pop(tunnel_id, None)

        service = BackendService.__new__(BackendService)
        service.manager = manager

        # The service checks the process state before delegating removal.
        result = service.dispatch("delete_tunnel", {"tunnel_id": "finished"})
        self.assertTrue(result["deleted"])
        manager.remove_finished.assert_called_once_with("finished")

        with self.assertRaises(ValueError):
            service.dispatch("delete_tunnel", {"tunnel_id": "running"})

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
