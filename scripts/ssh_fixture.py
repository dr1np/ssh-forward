"""Loopback-only SSH/HTTP fixture for real OpenSSH integration and desktop QA."""
import argparse
import json
import os
import select
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import paramiko


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"ssh-forwarder-integration-ok\n"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


class SSHFixture:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.directory = directory.resolve()
        self.host_key = paramiko.RSAKey.generate(2048)
        self.client_key = paramiko.RSAKey.generate(2048)
        self.key_path = self.directory / "test_key"
        self.client_key.write_private_key_file(str(self.key_path))
        if os.name == "nt":
            username = os.environ.get("USERNAME")
            if username:
                subprocess.run(
                    ["icacls", str(self.key_path), "/inheritance:r", "/grant:r", f"{username}:F"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
        else:
            self.key_path.chmod(0o600)
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen()
        self.listener.settimeout(0.2)
        self.ssh_port = self.listener.getsockname()[1]
        self.http_port = self.http.server_port
        self.stopped = threading.Event()
        self.transports = []
        self.config = self.directory / "ssh_config"
        self.config.write_text(
            f'Host qa-loopback\n  HostName 127.0.0.1\n  Port {self.ssh_port}\n  User qa\n'
            f'Host *\n  IdentityFile "{self.key_path.as_posix()}"\n  IdentitiesOnly yes\n'
            f'  UserKnownHostsFile "{(self.directory / "known_hosts").as_posix()}"\n', encoding="utf-8")
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        threading.Thread(target=self.accept, daemon=True).start()

    def accept(self):
        while not self.stopped.is_set():
            try:
                client, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self.serve, args=(client,), daemon=True).start()

    def serve(self, client):
        fixture = self

        class Server(paramiko.ServerInterface):
            def check_auth_publickey(self, username, key):
                matches = key.asbytes() == fixture.client_key.asbytes()
                return paramiko.AUTH_SUCCESSFUL if username == "qa" and matches else paramiko.AUTH_FAILED

            def get_allowed_auths(self, username):
                return "publickey"

            def check_channel_direct_tcpip_request(self, chanid, origin, destination):
                return paramiko.OPEN_SUCCEEDED if destination == ("127.0.0.1", fixture.http_port) else paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

        transport = paramiko.Transport(client)
        self.transports.append(transport)
        transport.add_server_key(self.host_key)
        try:
            transport.start_server(server=Server())
            while transport.is_active() and not self.stopped.is_set():
                channel = transport.accept(0.2)
                if channel is not None:
                    threading.Thread(target=self.relay, args=(channel,), daemon=True).start()
        except (EOFError, OSError, paramiko.SSHException):
            pass
        finally:
            transport.close()

    def relay(self, channel):
        try:
            with socket.create_connection(("127.0.0.1", self.http_port)) as target:
                while not self.stopped.is_set():
                    readable, _, _ = select.select([channel, target], [], [], 0.2)
                    for source in readable:
                        data = source.recv(65536)
                        if not data:
                            return
                        (target if source is channel else channel).sendall(data)
        except (EOFError, OSError):
            pass
        finally:
            channel.close()

    def close(self):
        self.stopped.set()
        self.listener.close()
        for transport in self.transports:
            transport.close()
        self.http.shutdown()
        self.http.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    fixture = SSHFixture(args.directory)
    metadata = {"ssh_port": fixture.ssh_port, "http_port": fixture.http_port, "config": str(fixture.config), "identity": str(fixture.key_path)}
    (args.directory / "fixture.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata), flush=True)
    try:
        while not (args.directory / "stop").exists():
            time.sleep(0.2)
    finally:
        fixture.close()
