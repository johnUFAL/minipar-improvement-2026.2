from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import run_testes_2026_2 as runner

ROOT = Path(__file__).resolve().parents[2]
PROGRAMS = {
    "t08": {
        "file": "t08_avaliacao_4_nucleos.mp",
        "cores": 4,
        "fractals": [],
    },
    "t09": {
        "file": "t09_5_nucleos_4_avaliadores_1_fractal.mp",
        "cores": 5,
        "fractals": ["FRACTAL DE MANDELBROT"],
    },
    "t10": {
        "file": "t10_6_nucleos_avaliacao_2_fractais.mp",
        "cores": 6,
        "fractals": ["FRACTAL DE MANDELBROT", "TAPETE DE SIERPINSKI"],
    },
}
SEQUENTIAL = re.compile(
    r"^\[Professor\] Concluiu 160 atividades \(checksum ([\d.]+)\)$",
    re.MULTILINE,
)
PARALLEL = re.compile(
    r"^\[(Professor|Monitor \d+)\] Concluiu 40 atividades \(checksum ([\d.]+)\)$",
    re.MULTILINE,
)


class TestT08T10(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.work = Path(cls.temp_dir.name)
        cls.executables: dict[str, Path] = {}
        cls.outputs: dict[str, str] = {}
        for key, spec in PROGRAMS.items():
            executable = runner.build_program(
                ROOT / "programas_teste" / spec["file"], cls.work, "O2"
            )
            if not executable.is_file():
                alternative = executable.with_suffix(".exe")
                if alternative.is_file():
                    executable = alternative
            cls.executables[key] = executable
            cls.outputs[key] = cls._run(executable)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "temp_dir"):
            cls.temp_dir.cleanup()

    @classmethod
    def _run(cls, executable: Path) -> str:
        result = subprocess.run(
            [str(executable)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            cwd=str(cls.work),
            timeout=180,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        return result.stdout.replace("\r\n", "\n")

    def test_output_markers(self) -> None:
        for key, spec in PROGRAMS.items():
            with self.subTest(program=key):
                output = self.outputs[key]
                self.assertIn("160", output)
                self.assertIn("BENCHMARK DE DESEMPENHO", output)
                self.assertIn(
                    f"Nucleos Utilizados (Paralelo) : {spec['cores']}",
                    output,
                )
                self.assertIn("[Professor] Concluiu 160 atividades", output)
                self.assertIn("Tempo Sequencial", output)
                self.assertIn("Tempo Paralelo", output)
                self.assertIn("Aceleracao", output)
                self.assertNotIn("Traceback", output)
                for fractal in spec["fractals"]:
                    self.assertIn(fractal, output)

    def test_four_parallel_workers_complete_forty_tasks_each(self) -> None:
        for key in PROGRAMS:
            with self.subTest(program=key):
                matches = PARALLEL.findall(self.outputs[key])
                self.assertEqual(len(matches), 4, self.outputs[key])
                workers = {worker for worker, _ in matches}
                self.assertEqual(
                    workers,
                    {"Professor", "Monitor 1", "Monitor 2", "Monitor 3"},
                )

    def test_sequential_and_parallel_checksums_agree(self) -> None:
        for key in PROGRAMS:
            with self.subTest(program=key):
                output = self.outputs[key]
                sequential = SEQUENTIAL.findall(output)
                parallel = PARALLEL.findall(output)
                self.assertEqual(len(sequential), 1, output)
                self.assertEqual(len(parallel), 4, output)
                sequential_total = float(sequential[0])
                parallel_total = sum(float(value) for _, value in parallel)
                self.assertAlmostEqual(
                    parallel_total, sequential_total, delta=0.05
                )


if __name__ == "__main__":
    unittest.main()
