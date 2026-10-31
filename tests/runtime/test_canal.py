from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CANAL_TEST = Path(__file__).with_name("canal_test.cpp")


class CppChannelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        compiler = os.environ.get("CXX", "g++").strip('"')
        compiler_path = shutil.which(compiler)
        if compiler_path is None:
            raise unittest.SkipTest(f"Compilador C++ nao encontrado: {compiler}")

        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.executable = Path(cls.temp_dir.name) / (
            "canal_test.exe" if os.name == "nt" else "canal_test"
        )
        command = [
            compiler_path,
            "-std=c++17",
            str(CANAL_TEST),
            str(ROOT / "runtime" / "canal.cpp"),
            "-I",
            str(ROOT / "runtime"),
            "-o",
            str(cls.executable),
        ]
        if os.name == "nt":
            command.append("-lws2_32")
        elif sys.platform.startswith("linux"):
            command.append("-pthread")
        result = subprocess.run(command, capture_output=True, check=False)
        if result.returncode:
            raise AssertionError(result.stderr.decode(errors="replace"))

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "temp_dir"):
            cls.temp_dir.cleanup()

    @staticmethod
    def _port() -> int:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    def _run(self, *arguments: str, timeout: float = 5) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [str(self.executable), *arguments],
            capture_output=True,
            check=False,
            timeout=timeout,
        )

    def test_two_processes_exchange_typed_and_ordered_messages(self) -> None:
        port = self._port()
        server = subprocess.Popen(
            [str(self.executable), "server", "10000", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            time.sleep(0.1)
            client = self._run("client", "500", str(port), timeout=10)
            self.assertEqual(client.returncode, 0, client.stderr.decode(errors="replace"))
            _, server_stderr = server.communicate(timeout=10)
            self.assertEqual(server.returncode, 0, server_stderr.decode(errors="replace"))
        finally:
            if server.poll() is None:
                server.kill()
                server.communicate(timeout=2)

    def test_refused_connection_fails_clearly(self) -> None:
        result = self._run("connect", "300", str(self._port()))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"conexao recusada", result.stderr)

    def test_string_compatibility_wrappers_use_the_framed_channel(self) -> None:
        port = self._port()
        server = subprocess.Popen(
            [str(self.executable), "legacy-server", "5000", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            time.sleep(0.1)
            client = self._run("legacy-client", "500", str(port))
            self.assertEqual(client.returncode, 0, client.stderr.decode(errors="replace"))
            _, server_stderr = server.communicate(timeout=5)
            self.assertEqual(server.returncode, 0, server_stderr.decode(errors="replace"))
        finally:
            if server.poll() is None:
                server.kill()
                server.communicate(timeout=2)

    def test_receive_times_out_instead_of_waiting_forever(self) -> None:
        port = self._port()
        listener = socket.socket()
        listener.bind(("127.0.0.1", port))
        listener.listen(1)

        def accept_and_wait() -> None:
            connection, _ = listener.accept()
            with connection:
                time.sleep(1)
            listener.close()

        worker = threading.Thread(target=accept_and_wait, daemon=True)
        worker.start()
        result = self._run("receive", "300", str(port), timeout=3)
        worker.join(timeout=2)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"Timeout ao receber", result.stderr)

    def test_server_termination_mid_message_is_reported(self) -> None:
        port = self._port()
        script = (
            "import socket, sys, time\n"
            "s=socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)\n"
            "s.bind(('127.0.0.1', int(sys.argv[1]))); s.listen(1); print('READY', flush=True)\n"
            "c,_=s.accept(); c.sendall(bytes.fromhex('0000000101000000080001'))\n"
            "print('PARTIAL', flush=True); time.sleep(30)\n"
        )
        peer = subprocess.Popen(
            [sys.executable, "-c", script, str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            self.assertEqual(peer.stdout.readline().strip(), "READY")
            client = subprocess.Popen(
                [str(self.executable), "receive", "5000", str(port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(peer.stdout.readline().strip(), "PARTIAL")
            peer.kill()
            peer.communicate(timeout=2)
            _, client_stderr = client.communicate(timeout=3)
            self.assertNotEqual(client.returncode, 0)
            self.assertIn(
                b"Conexao encerrada no meio de uma mensagem",
                client_stderr,
            )
        finally:
            if peer.poll() is None:
                peer.kill()
                peer.communicate(timeout=2)


if __name__ == "__main__":
    unittest.main()
