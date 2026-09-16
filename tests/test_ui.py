import queue
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from ssh_forwarder.models import ActiveTunnel, ForwardProfile
from ssh_forwarder.ui import SSHForwarderApp


class FinishedProcess:
    def poll(self) -> int:
        return 0


class RunningProcess:
    def poll(self) -> None:
        return None


class FakeTree:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, object]] = {}

    def exists(self, item_id: str) -> bool:
        return item_id in self.rows

    def delete(self, item_id: str) -> None:
        self.rows.pop(item_id, None)

    def item(self, item_id: str, **kwargs: object) -> None:
        self.rows[item_id] = kwargs


class UITests(unittest.TestCase):
    def test_finished_tunnel_elapsed_time_is_frozen(self) -> None:
        started_at = datetime.now() - timedelta(seconds=120)
        ended_at = started_at + timedelta(seconds=17)
        profile = ForwardProfile(
            name="test",
            ssh_host="server",
            local_port=18080,
            remote_host="127.0.0.1",
            remote_port=80,
        )
        active = ActiveTunnel(
            "tunnel-id",
            profile,
            FinishedProcess(),
            status="已停止",
            started_at=started_at,
            ended_at=ended_at,
        )
        tree = FakeTree()
        tree.rows[active.id] = {}
        app = SSHForwarderApp.__new__(SSHForwarderApp)
        app.manager = SimpleNamespace(snapshot=lambda: [active])
        app.active_tree = tree

        app._refresh_active_rows()

        self.assertEqual(tree.rows[active.id]["values"][-1], "00:17")
        self.assertEqual(tree.rows[active.id]["tags"], ("stopped",))

    def test_port_change_failure_keeps_running_old_tunnel_row(self) -> None:
        profile = ForwardProfile(
            name="test",
            ssh_host="server",
            local_port=18080,
            remote_host="127.0.0.1",
            remote_port=80,
        )
        active = ActiveTunnel("old-id", profile, RunningProcess(), status="运行中")
        tree = FakeTree()
        tree.rows[active.id] = {}
        app = SSHForwarderApp.__new__(SSHForwarderApp)
        app.manager = SimpleNamespace(get=lambda _tunnel_id: active)
        app.active_tree = tree
        app._async_results = queue.Queue()
        app._async_results.put(("port_error", active.id, "无法停止"))
        app.log = lambda *_args: None
        app.root = object()

        with patch("ssh_forwarder.ui.messagebox.showerror") as show_error:
            app._handle_async_results()

        self.assertTrue(tree.exists(active.id))
        self.assertIn("仍在运行", show_error.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
