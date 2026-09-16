import unittest

from ssh_forwarder.models import ForwardProfile
from ssh_forwarder.tunnel_manager import build_ssh_command


class ForwardProfileTests(unittest.TestCase):
    def test_config_host_command_uses_alias(self) -> None:
        profile = ForwardProfile(
            name="数据库",
            ssh_host="production",
            local_port=15432,
            remote_host="127.0.0.1",
            remote_port=5432,
        )
        command = build_ssh_command("ssh", profile)
        self.assertEqual(command[-1], "production")
        self.assertIn("127.0.0.1:15432:127.0.0.1:5432", command)
        self.assertIn("BatchMode=yes", command)

    def test_custom_host_command_includes_user_port_and_key(self) -> None:
        profile = ForwardProfile(
            name="Web",
            connection_type="custom",
            ssh_host="10.0.0.8",
            ssh_port=2222,
            ssh_user="alice",
            identity_file="C:/keys/work key",
            local_port=8080,
            remote_host="internal.example",
            remote_port=80,
        )
        command = build_ssh_command("ssh.exe", profile)
        self.assertEqual(command[-1], "alice@10.0.0.8")
        self.assertEqual(command[command.index("-p") + 1], "2222")
        self.assertEqual(command[command.index("-i") + 1], "C:\\keys\\work key")

    def test_ipv6_forward_spec_is_bracketed(self) -> None:
        profile = ForwardProfile(
            name="IPv6",
            ssh_host="server",
            local_bind="::1",
            local_port=8080,
            remote_host="2001:db8::1",
            remote_port=80,
        )
        command = build_ssh_command("ssh", profile)
        self.assertIn("[::1]:8080:[2001:db8::1]:80", command)
        self.assertEqual(profile.local_endpoint, "[::1]:8080")
        self.assertEqual(profile.target_endpoint, "[2001:db8::1]:80")

    def test_invalid_port_is_rejected(self) -> None:
        profile = ForwardProfile(
            name="bad",
            ssh_host="server",
            local_port=70000,
            remote_host="localhost",
            remote_port=80,
        )
        with self.assertRaises(ValueError):
            profile.validate()

    def test_non_integer_port_is_rejected(self) -> None:
        for value in (True, 1.5, "8080"):
            profile = ForwardProfile(
                name="bad",
                ssh_host="server",
                local_port=value,
                remote_host="localhost",
                remote_port=80,
            )
            with self.subTest(value=value), self.assertRaises(ValueError):
                profile.validate()

    def test_from_dict_rejects_non_mapping(self) -> None:
        with self.assertRaises(ValueError):
            ForwardProfile.from_dict(None)


if __name__ == "__main__":
    unittest.main()
