import tempfile
import unittest
from pathlib import Path

from ssh_forwarder.ssh_config import discover_ssh_hosts


class SSHConfigTests(unittest.TestCase):
    def test_discovers_hosts_and_follows_includes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config"
            included = root / "work.conf"
            config.write_text(
                "Host alpha beta\n"
                "  HostName 192.0.2.1\n"
                "Host *.example !blocked\n"
                "Include work.conf\n",
                encoding="utf-8",
            )
            included.write_text("Host=gamma\nHost = delta\nHost ALPHA\n", encoding="utf-8")

            self.assertEqual(discover_ssh_hosts(config), ["alpha", "beta", "gamma", "delta"])

    def test_missing_config_returns_empty_list(self) -> None:
        self.assertEqual(discover_ssh_hosts(Path("definitely-missing-config")), [])


if __name__ == "__main__":
    unittest.main()
