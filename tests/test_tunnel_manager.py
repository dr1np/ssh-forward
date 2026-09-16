import subprocess
import threading
import time
import unittest
from unittest.mock import patch

from ssh_forwarder.models import ActiveTunnel, ForwardProfile
from ssh_forwarder.tunnel_manager import TunnelManager


def make_profile(local_port: int = 18080) -> ForwardProfile:
    return ForwardProfile(
        name="test",
        ssh_host="server",
        local_port=local_port,
        remote_host="127.0.0.1",
        remote_port=80,
    )


class FakeStderr:
    def readline(self) -> str:
        return ""

    def close(self) -> None:
        return None


class FakeProcess:
    def __init__(
        self,
        *,
        terminate_error: OSError | None = None,
        wait_always_times_out: bool = False,
    ) -> None:
        self.returncode: int | None = None
        self.stderr = FakeStderr()
        self.terminate_error = terminate_error
        self.wait_always_times_out = wait_always_times_out
        self.wait_finished = threading.Event()

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        if self.terminate_error is not None:
            raise self.terminate_error
        if not self.wait_always_times_out:
            self.returncode = 0

    def kill(self) -> None:
        if not self.wait_always_times_out:
            self.returncode = 0

    def wait(self, timeout: float | None = None) -> int:
        if self.wait_always_times_out:
            raise subprocess.TimeoutExpired(["ssh"], timeout)
        if self.returncode is None:
            self.returncode = 0
        self.wait_finished.set()
        return self.returncode


class TunnelManagerTests(unittest.TestCase):
    @patch("ssh_forwarder.tunnel_manager.is_local_port_available", return_value=True)
    @patch("ssh_forwarder.tunnel_manager.subprocess.Popen")
    def test_process_watcher_records_end_time(
        self, popen: object, _port_available: object
    ) -> None:
        process = FakeProcess()
        popen.return_value = process  # type: ignore[attr-defined]
        manager = TunnelManager(ssh_executable="ssh")

        active = manager.start(make_profile())

        self.assertTrue(process.wait_finished.wait(1))
        for _ in range(100):
            if active.ended_at is not None:
                break
            time.sleep(0.001)
        self.assertIsNotNone(active.ended_at)
        self.assertEqual(active.status, "已结束")

    def test_stop_failure_restores_previous_status(self) -> None:
        manager = TunnelManager(ssh_executable="ssh")
        active = ActiveTunnel(
            "tunnel-id",
            make_profile(),
            FakeProcess(terminate_error=OSError("permission denied")),
            status="运行中",
        )
        manager.tunnels[active.id] = active

        with self.assertRaises(OSError):
            manager.stop(active.id)

        self.assertEqual(active.status, "运行中")
        self.assertIsNone(active.ended_at)

    def test_stop_timeout_becomes_runtime_error_and_restores_status(self) -> None:
        manager = TunnelManager(ssh_executable="ssh")
        active = ActiveTunnel(
            "tunnel-id",
            make_profile(),
            FakeProcess(wait_always_times_out=True),
            status="运行中",
        )
        manager.tunnels[active.id] = active

        with self.assertRaisesRegex(RuntimeError, "未能在超时后停止"):
            manager.stop(active.id)

        self.assertEqual(active.status, "运行中")

    def test_shutdown_prevents_new_processes(self) -> None:
        manager = TunnelManager(ssh_executable="ssh")
        self.assertEqual(manager.shutdown(), [])

        with self.assertRaisesRegex(RuntimeError, "应用正在关闭"):
            manager.start(make_profile(18081))


if __name__ == "__main__":
    unittest.main()
