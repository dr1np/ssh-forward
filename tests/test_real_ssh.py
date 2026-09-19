"""Real OpenSSH forwarding to an isolated local SSH server (optional test dependency)."""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from unittest.mock import patch

try:
    from scripts.ssh_fixture import SSHFixture
except ImportError:
    SSHFixture = None

from ssh_forwarder.models import ForwardProfile
from ssh_forwarder.tunnel_manager import TunnelManager, find_available_port


@unittest.skipUnless(SSHFixture and shutil.which("ssh"), "Install requirements-test.txt and OpenSSH for real integration tests")
class RealSSHTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.fixture = SSHFixture(Path(self.temporary.name))
        self.env = patch.dict(os.environ, {"SSH_FORWARDER_SSH_CONFIG": str(self.fixture.config), "SSH_FORWARDER_DATA_DIR": self.temporary.name})
        self.env.start()
        self.manager = TunnelManager()

    def tearDown(self):
        self.manager.shutdown()
        self.fixture.close()
        self.env.stop()
        self.temporary.cleanup()

    def make_profile(self, **changes):
        values = dict(name="integration", ssh_host="qa-loopback", local_port=find_available_port(), remote_host="127.0.0.1", remote_port=self.fixture.http_port)
        values.update(changes)
        return ForwardProfile(**values)

    def ready(self, tunnel):
        deadline = time.monotonic() + 10
        while not self.manager.mark_connected_if_running(tunnel.id):
            if time.monotonic() > deadline or tunnel.process.poll() is not None:
                if tunnel.process.poll() is not None and not tunnel.last_error:
                    time.sleep(0.2)
                self.fail(
                    f"SSH failed: {tunnel.status}: {tunnel.last_error!r}; "
                    f"returncode={tunnel.process.poll()!r}; args={getattr(tunnel.process, 'args', None)!r}"
                )
            time.sleep(0.05)

    def request(self, port):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"http://127.0.0.1:{port}/", timeout=5) as response:
            self.assertEqual(response.read(), b"ssh-forwarder-integration-ok\n")

    def test_forward_conflict_change_stop_restart_and_multiple_connections(self):
        first = self.manager.start(self.make_profile())
        self.ready(first)
        self.request(first.profile.local_port)
        with socket.socket() as occupied:
            occupied.bind(("127.0.0.1", 0))
            with self.assertRaisesRegex(RuntimeError, "已被占用"):
                self.manager.change_port(first.id, occupied.getsockname()[1])
        self.request(first.profile.local_port)
        second = self.manager.start(self.make_profile(connection_type="custom", ssh_host="127.0.0.1", ssh_user="qa", ssh_port=self.fixture.ssh_port, identity_file=str(self.fixture.key_path)))
        self.ready(second)
        self.request(second.profile.local_port)
        replacement = self.manager.change_port(first.id, find_available_port())
        self.request(replacement.profile.local_port)
        self.assertIsNotNone(first.process.poll())
        self.manager.stop(replacement.id)
        self.assertIsNotNone(replacement.process.poll())
        restarted = self.manager.start(replacement.profile)
        self.ready(restarted)
        self.request(restarted.profile.local_port)
        self.assertEqual(self.manager.shutdown(), [])
        self.assertEqual(self.manager.running_count(), 0)

    def test_authentication_failure_never_becomes_running(self):
        tunnel = self.manager.start(self.make_profile(connection_type="custom", ssh_host="127.0.0.1", ssh_user="wrong", ssh_port=self.fixture.ssh_port))
        deadline = time.monotonic() + 10
        while tunnel.process.poll() is None and time.monotonic() < deadline:
            self.assertFalse(self.manager.mark_connected_if_running(tunnel.id))
            time.sleep(0.05)
        self.assertIsNotNone(tunnel.process.poll())
        self.assertNotEqual(tunnel.status, "运行中")


if __name__ == "__main__":
    unittest.main()
