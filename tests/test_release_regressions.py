import os
import socket
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ssh_forwarder.models import ActiveTunnel, ForwardProfile
from ssh_forwarder.service import BackendService
from ssh_forwarder.storage import ProfileStore, default_data_file
from ssh_forwarder.tunnel_manager import TunnelManager


def profile(port=18080):
    return ForwardProfile(name="test", ssh_host="localhost", local_port=port, remote_host="127.0.0.1", remote_port=80)


class ReleaseRegressions(unittest.TestCase):
    def test_live_process_without_listener_is_not_connected(self):
        manager = TunnelManager("ssh")
        tunnel = ActiveTunnel("pending", profile(), SimpleNamespace(poll=lambda: None))
        manager.tunnels[tunnel.id] = tunnel
        with patch("socket.create_connection", side_effect=ConnectionRefusedError):
            self.assertFalse(manager.mark_connected_if_running(tunnel.id))
        self.assertEqual(tunnel.status, "正在连接")

    def test_running_requires_listener_and_live_process(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            manager = TunnelManager("ssh")
            tunnel = ActiveTunnel("pending", profile(listener.getsockname()[1]), SimpleNamespace(poll=lambda: None))
            manager.tunnels[tunnel.id] = tunnel
            self.assertTrue(manager.mark_connected_if_running(tunnel.id))
            self.assertEqual(tunnel.status, "运行中")

    def test_invalid_or_occupied_new_port_keeps_old_connection(self):
        manager = TunnelManager("ssh")
        process = Mock()
        process.poll.return_value = None
        tunnel = ActiveTunnel("old", profile(), process, status="运行中")
        manager.tunnels[tunnel.id] = tunnel
        for invalid in [0, 65536, True, 1.5, "80"]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                manager.change_port(tunnel.id, invalid)
        with socket.socket() as occupied:
            occupied.bind(("127.0.0.1", 0))
            with self.assertRaisesRegex(RuntimeError, "已被占用"):
                manager.change_port(tunnel.id, occupied.getsockname()[1])
        process.terminate.assert_not_called()
        self.assertEqual(tunnel.status, "运行中")
        self.assertIs(manager.change_port(tunnel.id, 18080), tunnel)

    def test_failed_replacement_keeps_old_connection(self):
        manager = TunnelManager("ssh")
        old = ActiveTunnel("old", profile(), SimpleNamespace(poll=lambda: None), status="运行中")
        failed = ActiveTunnel("failed", profile(18081), SimpleNamespace(poll=lambda: 1), status="连接失败")
        manager.tunnels[old.id] = old
        with patch.object(manager, "start", return_value=failed), patch.object(manager, "stop") as stop:
            with self.assertRaisesRegex(RuntimeError, "原转发保持运行"):
                manager.change_port("old", 18081)
            stop.assert_called_once_with("failed")

    def test_eof_shuts_down_manager(self):
        service = BackendService.__new__(BackendService)
        import queue
        import threading
        service.requests = queue.Queue()
        service.requests.put({"_eof": True})
        service.stop_requested = threading.Event()
        service.manager = Mock()
        with patch.object(service, "request_reader"):
            service.run()
        service.manager.shutdown.assert_called_once()

    def test_damaged_store_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text("{broken", encoding="utf-8")
            store = ProfileStore(path)
            with self.assertRaises(ValueError): store.load()
            with self.assertRaises(ValueError): store.upsert(profile())
            with self.assertRaises(ValueError): store.delete("missing")
            self.assertEqual(path.read_text(encoding="utf-8"), "{broken")

    def test_cross_platform_paths(self):
        with patch.dict(os.environ, {"SSH_FORWARDER_DATA_DIR": ""}):
            with patch("sys.platform", "darwin"):
                self.assertIn("Application Support", str(default_data_file()))
            with patch("sys.platform", "linux"), patch.dict(os.environ, {"XDG_CONFIG_HOME": "/tmp/config"}):
                self.assertEqual(default_data_file(), Path("/tmp/config/SSHForwarder/settings.json"))

    def test_option_like_or_whitespace_hosts_rejected(self):
        for host in ["-oProxyCommand=bad", "two hosts", "bad\nname"]:
            item = profile()
            item.ssh_host = host
            with self.assertRaises(ValueError): item.validate()


if __name__ == "__main__":
    unittest.main()
