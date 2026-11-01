from __future__ import annotations

import os
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from components.codegen.c_gerador_cpp import CppCodeGenerator
from components.codegen.driver_gcc import DriverGCC
from components.lexico import Lexer
from components.semantico.c_semantico import SemanticAnalyzer
from components.sintatico.c_sintatico import Parser
from components.tac.c_gerador_tac import TACGenerator


ROOT = Path(__file__).resolve().parents[2]


class RemoteForkIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        compiler = os.environ.get("CXX", "g++").strip('"')
        if shutil.which(compiler) is None:
            raise unittest.SkipTest(f"Compilador C++ nao encontrado: {compiler}")

        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temp_dir.name)
        suffix = ".exe" if os.name == "nt" else ""
        cls.executable = cls.directory / f"remote_fork{suffix}"
        cpp_path = cls.directory / "remote_fork.cpp"
        source = """SEQ
    input_a: int = 7
    input_b: string = "hello"
    input_c: float = 1.5
    input_d: bool = true
    result_a: int = 0
    result_b: string = ""
    result_c: float = 0.0
    result_d: bool = false
    fork remote_a em host("worker_a"):
        result_a = input_a + 1
        result_b = input_b + " remoto"
    fork remote_b em host("worker_b"):
        result_c = input_c / 2
        result_d = not input_d
    join remote_a, remote_b
    print(result_a, result_b, result_c, result_d)
        """
        program = Parser(Lexer(source)).parse()
        analyzer = SemanticAnalyzer()
        if not analyzer.analyze(program):
            raise AssertionError(f"Falha na analise semantica: {analyzer.diagnostics}")
        tac = TACGenerator().generate_text(program)
        cpp_path.write_text(CppCodeGenerator._generate_cpp(tac), encoding="utf-8")
        if not DriverGCC().compilar(cpp_path, cls.executable, "O0"):
            raise AssertionError("Falha ao compilar fork remoto.")

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "temp_dir"):
            cls.temp_dir.cleanup()

    @staticmethod
    def _port() -> int:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    def test_two_remote_tasks_return_results_at_join(self) -> None:
        ports = (self._port(), self._port())
        hosts_path = self.directory / "localhost.hosts"
        hosts_path.write_text(
            f"worker_a = 127.0.0.1:{ports[0]}\n"
            f"worker_b = 127.0.0.1:{ports[1]}\n",
            encoding="utf-8",
        )
        workers = [
            subprocess.Popen(
                [str(self.executable.with_name("minipar_worker" + self.executable.suffix)),
                 "--porta", str(port)],
                cwd=self.directory,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for port in ports
        ]
        try:
            time.sleep(0.15)
            for worker in workers:
                self.assertIsNone(worker.poll(), "Worker terminou antes do pedido.")

            result = subprocess.run(
                [str(self.executable), "--hosts", str(hosts_path)],
                cwd=self.directory,
                capture_output=True,
                check=False,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "8 hello remoto 0.75 0")
        finally:
            for worker in workers:
                if worker.poll() is None:
                    worker.terminate()
                worker.communicate(timeout=3)

    def test_unavailable_worker_fails_within_configured_timeout(self) -> None:
        hosts_path = self.directory / "unavailable.hosts"
        hosts_path.write_text(
            f"worker_a = 127.0.0.1:{self._port()}\n"
            f"worker_b = 127.0.0.1:{self._port()}\n",
            encoding="utf-8",
        )
        environment = os.environ.copy()
        environment["MINIPAR_TIMEOUT_MS"] = "250"
        started = time.monotonic()
        result = subprocess.run(
            [str(self.executable), "--hosts", str(hosts_path)],
            cwd=self.directory,
            capture_output=True,
            check=False,
            text=True,
            timeout=3,
            env=environment,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("conexao recusada ou timeout", result.stderr)
        self.assertLess(time.monotonic() - started, 3)


if __name__ == "__main__":
    unittest.main()
