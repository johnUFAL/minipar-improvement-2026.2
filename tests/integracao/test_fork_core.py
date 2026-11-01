from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from components.codegen.c_gerador_cpp import CppCodeGenerator


class ForkCoreIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        compiler = os.environ.get("CXX", "g++").strip('"')
        compiler_path = shutil.which(compiler)
        if compiler_path is None:
            raise unittest.SkipTest(f"Compilador C++ nao encontrado: {compiler}")

        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.executables: dict[int, Path] = {}
        suffix = ".exe" if os.name == "nt" else ""
        for core in (1, 99):
            executable = Path(cls.temp_dir.name) / f"fork_core_{core}{suffix}"
            cpp_path = Path(cls.temp_dir.name) / f"fork_core_{core}.cpp"
            tac = f"""goto MAIN
MAIN:
requested_core:int = {core}
par_begin 1
fork worker, core, requested_core, BRANCH
join worker
goto END
BRANCH:
print 'executed'
join worker
END:
par_end
"""
            cpp_path.write_text(
                CppCodeGenerator._generate_cpp(tac), encoding="utf-8"
            )
            command = [
                compiler_path,
                "-std=c++17",
                str(cpp_path),
                str(Path(__file__).resolve().parents[2] / "runtime" / "canal.cpp"),
                str(Path(__file__).resolve().parents[2] / "runtime" / "paralelo.cpp"),
                "-I",
                str(Path(__file__).resolve().parents[2] / "runtime"),
                "-pthread",
                "-o",
                str(executable),
            ]
            if os.name == "nt":
                command.append("-lws2_32")
            result = subprocess.run(
                command,
                capture_output=True,
                check=False,
                text=True,
            )
            if result.returncode:
                raise AssertionError(
                    "Falha ao compilar teste de afinidade:\n" + result.stderr
                )
            cls.executables[core] = executable

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "temp_dir"):
            cls.temp_dir.cleanup()

    @unittest.skipUnless(
        sys.platform.startswith("linux") or os.name == "nt",
        "Afinidade aplicada e verificada no Linux e Windows",
    )
    def test_requested_core_runs_and_reports_cpu(self) -> None:
        environment = os.environ.copy()
        environment["MINIPAR_TRACE_CORES"] = "1"
        result = subprocess.run(
            [str(self.executables[1])],
            capture_output=True,
            check=False,
            text=True,
            env=environment,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "executed")
        self.assertRegex(result.stderr, r"tarefa worker executou no CPU \d+")
        self.assertNotIn("Aviso:", result.stderr)

    def test_unavailable_core_warns_but_executes_task(self) -> None:
        command = [str(self.executables[99])]
        taskset = shutil.which("taskset")
        if (
            sys.platform.startswith("linux")
            and taskset is not None
            and hasattr(os, "sched_getaffinity")
        ):
            allowed = os.sched_getaffinity(0)
            if allowed:
                command = [taskset, "-c", str(min(allowed)), *command]
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "executed")
        self.assertIn("core(99)", result.stderr)
        self.assertIn("CPUs disponiveis", result.stderr)

    @unittest.skipUnless(
        sys.platform.startswith("linux") and hasattr(os, "sched_getaffinity"),
        "Teste de taskset disponivel somente no Linux",
    )
    def test_taskset_restriction_matches_reported_cpu(self) -> None:
        taskset = shutil.which("taskset")
        if taskset is None:
            self.skipTest("taskset nao encontrado")

        allowed = os.sched_getaffinity(0)
        selected_cpu = min(allowed)
        environment = os.environ.copy()
        environment["MINIPAR_TRACE_CORES"] = "1"
        result = subprocess.run(
            [
                taskset,
                "-c",
                str(selected_cpu),
                str(self.executables[1]),
            ],
            capture_output=True,
            check=False,
            text=True,
            env=environment,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            f"executou no CPU {selected_cpu}",
            result.stderr,
        )


if __name__ == "__main__":
    unittest.main()
