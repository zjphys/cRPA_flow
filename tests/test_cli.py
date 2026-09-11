"""Portable initialization checks; installed Linux execution is tested separately."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vasp_workflow.cli import main


class InitializationTests(unittest.TestCase):
    def invoke(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return main(list(map(str, args)))

    def test_init_does_not_overwrite_inputs_and_records_release(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input"
            source.write_text("original structure\n")
            case = root / "case with spaces"
            self.assertEqual(self.invoke("init", case, "--poscar", source), 0)
            conf = (case / "workflow.conf").read_text()
            self.assertIn("srun vasp_std", conf)
            self.assertNotIn("q_ysuan", conf)
            self.assertNotIn("/sh3/", conf)
            self.assertEqual(json.loads((case / ".workflow-release.json").read_text())["profile"], "slurm")
            (case / "POSCAR").write_text("changed by researcher")
            self.assertEqual(self.invoke("init", case, "--poscar", source), 1)
            self.assertEqual((case / "POSCAR").read_text(), "changed by researcher")

    def test_custom_configuration_is_copied_verbatim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "custom.conf"
            config.write_text("ENCUT=650\nRUN_RELAX=no\n")
            self.assertEqual(self.invoke("--config", config, "init", root / "case"), 0)
            self.assertEqual((root / "case/workflow.conf").read_text(), config.read_text())

    def test_bad_config_and_missing_input_leave_no_case(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case = root / "case"
            self.assertEqual(self.invoke("--config", root / "missing", "init", case), 1)
            self.assertFalse(case.exists())
            self.assertEqual(self.invoke("init", case, "--poscar", root / "missing"), 1)
            self.assertFalse(case.exists())

    def test_local_profile_has_no_slurm_runtime_variable(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.invoke("init", directory, "--profile", "local"), 0)
            config = (Path(directory) / "workflow.conf").read_text()
            self.assertNotIn("SLURM_NTASKS", config)
            self.assertIn("[default]='vasp_std'", config)


if __name__ == "__main__":
    unittest.main()
