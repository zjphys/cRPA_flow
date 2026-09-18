"""Exercise real Bash dispatch with isolated homes and a stateful fake scheduler."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "src/crpa_workflow/resources/workflow.sh"


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "Linux/Bash required")
class SubmissionSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="submission-safety-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.case = self.root / "case"
        self.case.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.state = self.root / "scheduler.json"
        self.state.write_text(json.dumps({"jobs": {}, "calls": [], "next": 1000}))
        scheduler = f"#!{sys.executable}\n" + r'''
import json, os, pathlib, sys
root = pathlib.Path(os.environ["MOCK_ROOT"])
path = root / "scheduler.json"
data = json.loads(path.read_text())
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
if "" in args:
    print("unexpected empty scheduler argument", file=sys.stderr)
    sys.exit(2)
if name == "sbatch":
    stage = pathlib.Path.cwd().name
    if (root / "reject").exists() and (root / "reject").read_text() == stage:
        print("mock scheduler rejected " + stage, file=sys.stderr)
        sys.exit(1)
    job = str(data["next"])
    data["next"] += 1
    data["jobs"][job] = "PENDING"
    data["calls"].append({"stage": stage, "args": args, "id": job})
    path.write_text(json.dumps(data))
    print("unexpected scheduler response" if (root / "malformed").exists()
          else job + (";alpha" if (root / "cluster").exists() else ""))
    if (root / "accepted-error").exists():
        sys.exit(1)
else:
    if (root / "query-fails").exists():
        sys.exit(1)
    job = next(x.split("=", 1)[1] for x in args if x.startswith("--jobs="))
    state = data["jobs"].get(job)
    if state:
        if name == "squeue":
            if state in ("PENDING", "RUNNING", "COMPLETING", "SUSPENDED"):
                print(state)
        else:
            print(job + "|" + state)
'''
        for name in ("sbatch", "squeue", "sacct"):
            path = self.bin / name
            path.write_text(scheduler)
            path.chmod(0o755)
        vaspkit = self.bin / "vaspkit"
        vaspkit.write_text("""#!/usr/bin/env bash
[[ ! -f "$MOCK_ROOT/preparation-fails" ]] || exit 1
read -r task
case "$task" in
  103) printf 'ENMAX = 400;\\n' > POTCAR ;;
  102) printf 'Gamma\\n0\\nGamma\\n2 2 2\\n0 0 0\\n' > KPOINTS ;;
  303) printf 'Path\\n10\\nLine-mode\\nReciprocal\\n0 0 0\\n0.5 0 0\\n' > KPATH.in ;;
esac
""")
        vaspkit.chmod(0o755)
        self.config = self.case / "workflow.conf"
        self.config.write_text("""VASPKIT_BIN=vaspkit
SUBMIT_COMMAND=sbatch
RUN_RELAX=yes
GENERATE_BANDS=yes
declare -A STAGE_COMMANDS=([default]='printf "%s" "${REVIEW_STACK:-unset}" > executed')
""")
        (self.case / "POSCAR").write_text("Si\n1\n1 0 0\n0 1 0\n0 0 1\nSi\n1\nDirect\n0 0 0\n")
        home = self.root / "home"
        home.mkdir()
        (home / ".bash_profile").write_text("export REVIEW_STACK=login-stack\n")
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("WORKFLOW_", "SLURM_", "SBATCH_"))
                    and k not in ("BASH_ENV", "ENV", "PYTHON_BIN")}
        self.env.update(WORKFLOW_ROOT=str(self.case), MOCK_ROOT=str(self.root),
                        HOME=str(home), REVIEW_STACK="configured-stack",
                        PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                        PYTHONPATH=str(REPO / "src"))
        self.workflow("prepare", ok=True)

    def workflow(self, *args, ok=None):
        result = subprocess.run(["bash", str(BACKEND), *args], cwd=self.case,
                                env=self.env, capture_output=True, text=True, timeout=20)
        if ok is True:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        elif ok is False:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def data(self):
        return json.loads(self.state.read_text())

    def finish(self, state="COMPLETED"):
        data = self.data()
        data["jobs"] = {job: state for job in data["jobs"]}
        self.state.write_text(json.dumps(data))

    def job(self, stage="00_relax"):
        return subprocess.run(["bash", str(self.case / stage / "job.sh")],
                              env=self.env, capture_output=True, text=True, timeout=20)

    def batch(self, *extra):
        structures = self.root / "structures"
        structures.mkdir(exist_ok=True)
        shutil.copy(self.case / "POSCAR", structures / "POSCAR_Si")
        return subprocess.run([sys.executable, "-m", "crpa_workflow", "--config",
                               str(self.config), "batch", "--mode", "submit", *extra,
                               str(structures), str(self.root / "calculations")],
                              cwd=self.case, env=self.env, capture_output=True,
                              text=True, timeout=20)

    def test_runtime_preserves_configured_environment(self):
        self.workflow("execute", "00_relax", ok=True)
        self.assertEqual((self.case / "00_relax/executed").read_text(), "configured-stack")
        self.assertEqual(self.job().returncode, 0)
        self.assertEqual((self.case / "00_relax/executed").read_text(), "configured-stack")

    def test_header_setup_failure_stops_before_simulation(self):
        with self.config.open("a") as f:
            f.write("\nSBATCH_TEMPLATE=$'#SBATCH --nodes=1\\nsource /nonexistent/vasp-env-review.sh'\n")
        self.workflow("prepare", "--force", ok=True)
        result = self.job()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.case / "00_relax/executed").exists())
        text = (self.case / "00_relax/job.sh").read_text()
        self.assertLess(text.index("#SBATCH"), text.index("set -euo"))
        self.assertLess(text.index("set -euo"), text.index("source /"))

    def test_directive_after_runtime_code_is_rejected(self):
        with self.config.open("a") as f:
            f.write("\nSBATCH_TEMPLATE=$'true\\n#SBATCH --nodes=1'\n")
        self.workflow("prepare", "--force", ok=False)

    def test_all_scripts_checked_before_first_submission(self):
        (self.case / "02_dos/job.sh").unlink()
        self.workflow("submit", ok=False)
        self.assertEqual(self.data()["calls"], [])

    def test_invalid_shell_script_checked_before_first_submission(self):
        (self.case / "03_band/job.sh").write_text("#!/bin/bash\nif then\n")
        self.workflow("submit", ok=False)
        self.assertEqual(self.data()["calls"], [])

    def test_partial_retry_reuses_jobs_and_dependency_ids(self):
        reject = self.root / "reject"
        reject.write_text("02_dos")
        self.workflow("submit", ok=False)
        self.assertEqual([c["stage"] for c in self.data()["calls"]], ["00_relax", "01_scf"])
        reject.unlink()
        self.workflow("submit", ok=True)
        calls = self.data()["calls"]
        self.assertEqual([c["stage"] for c in calls], ["00_relax", "01_scf", "02_dos", "03_band"])
        for call in calls[2:]:
            self.assertIn("--dependency=afterok:" + calls[1]["id"], call["args"])
        self.workflow("submit", ok=True)
        self.assertEqual(len(self.data()["calls"]), 4)

    def test_completed_jobs_reused_and_explicit_resubmit_creates_new_chain(self):
        self.workflow("submit", ok=True)
        self.finish()
        self.workflow("submit", ok=True)
        self.assertEqual(len(self.data()["calls"]), 4)
        self.workflow("submit", "--resubmit", "--job-name", "retry", ok=True)
        calls = self.data()["calls"]
        self.assertEqual(len(calls), 8)
        self.assertIn("--dependency=afterok:" + calls[4]["id"], calls[5]["args"])
        self.assertIn("--job-name=retry-scf", calls[5]["args"])

    def test_resume_after_completed_parent_needs_no_obsolete_dependency(self):
        reject = self.root / "reject"
        reject.write_text("02_dos")
        self.workflow("submit", ok=False)
        self.finish()
        reject.unlink()
        self.workflow("submit", ok=True)
        for call in self.data()["calls"][2:]:
            self.assertFalse(any(arg.startswith("--dependency=") for arg in call["args"]))
        self.workflow("submit", ok=True)
        self.assertEqual(len(self.data()["calls"]), 4)

    def test_partial_explicit_resubmit_can_resume_without_repeating_new_jobs(self):
        self.workflow("submit", ok=True)
        self.finish()
        reject = self.root / "reject"
        reject.write_text("02_dos")
        self.workflow("submit", "--resubmit", ok=False)
        self.assertEqual(len(self.data()["calls"]), 6)
        reject.unlink()
        self.workflow("submit", ok=True)
        self.assertEqual(len(self.data()["calls"]), 8)

    def test_resubmit_rejected_while_any_recorded_job_active(self):
        self.workflow("submit", ok=True)
        self.workflow("submit", "--resubmit", ok=False)
        self.assertEqual(len(self.data()["calls"]), 4)

    def test_failed_jobs_require_explicit_resubmit(self):
        self.workflow("submit", ok=True)
        self.finish("FAILED")
        self.workflow("submit", ok=False)
        self.workflow("submit", "--resubmit", ok=True)
        self.assertEqual(len(self.data()["calls"]), 8)

    def test_query_failures_and_missing_accounting_fail_closed(self):
        self.workflow("submit", ok=True)
        marker = self.root / "query-fails"
        marker.touch()
        self.workflow("submit", ok=False)
        self.workflow("submit", "--resubmit", ok=False)
        marker.unlink()
        data = self.data()
        data["jobs"] = {}
        self.state.write_text(json.dumps(data))
        self.workflow("submit", ok=False)
        self.assertEqual(len(self.data()["calls"]), 4)

    def test_changed_script_is_not_silently_reused(self):
        self.workflow("submit", ok=True)
        with (self.case / "02_dos/job.sh").open("a") as f:
            f.write("\n# changed resources\n")
        self.workflow("submit", ok=False)
        self.assertEqual(len(self.data()["calls"]), 4)

    def test_ambiguous_scheduler_response_blocks_retry(self):
        (self.root / "malformed").touch()
        self.workflow("submit", ok=False)
        self.assertTrue((self.case / ".workflow-submissions/00_relax.pending").exists())
        self.workflow("submit", ok=False)
        self.assertEqual(len(self.data()["calls"]), 1)

    def test_nonzero_exit_with_job_id_is_not_safe_to_retry(self):
        (self.root / "accepted-error").touch()
        self.workflow("submit", ok=False)
        self.workflow("submit", ok=False)
        self.assertEqual(len(self.data()["calls"]), 1)

    def test_cancelled_accounting_state_with_user_suffix_allows_resubmit(self):
        self.workflow("submit", ok=True)
        self.finish("CANCELLED by 12345")
        self.workflow("submit", "--resubmit", ok=True)
        self.assertEqual(len(self.data()["calls"]), 8)

    def test_concurrent_submission_lock(self):
        import fcntl
        with (self.case / ".workflow-submit.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.workflow("submit", ok=False)
        self.assertEqual(self.data()["calls"], [])

    def test_cluster_is_preserved_for_dependent_submissions(self):
        (self.root / "cluster").touch()
        self.workflow("submit", ok=True)
        for call in self.data()["calls"][1:]:
            self.assertIn("--clusters=alpha", call["args"])
        self.workflow("submit", ok=True)
        self.assertEqual(len(self.data()["calls"]), 4)

    def test_single_stage_submission_reuses_and_guards_jobs(self):
        for stage, command in (("04_wann", "submit-wannier"), ("05_crpa", "submit-crpa")):
            directory = self.case / stage
            directory.mkdir()
            (directory / ".generated-by-poscar-workflow").touch()
            (directory / "job.sh").write_text("#!/bin/bash\ntrue\n")
            with (self.case / ".workflow-stages").open("a") as f:
                f.write(stage + "\n")
            self.workflow(command, ok=True)
            self.workflow(command, ok=True)
            self.workflow(command, "--resubmit", ok=False)
        self.assertEqual(len(self.data()["calls"]), 2)

    def test_crpa_empty_options_and_queries_preserve_exact_arguments(self):
        directory = self.case / "05_crpa"
        directory.mkdir()
        (directory / ".generated-by-poscar-workflow").touch()
        (directory / "job.sh").write_text("#!/bin/bash\ntrue\n")
        with (self.case / ".workflow-stages").open("a") as f:
            f.write("05_crpa\n")
        self.workflow("submit-crpa", "--job-name", "Ce Ru", ok=True)
        self.assertEqual(self.data()["calls"][0]["args"],
                         ["--parsable", "--job-name=Ce Ru-crpa", "job.sh"])
        self.workflow("submit-crpa", ok=True)  # Empty cluster args in squeue.
        self.finish()
        self.workflow("submit-crpa", ok=True)  # Empty cluster args in sacct.
        self.assertEqual(len(self.data()["calls"]), 1)
        self.workflow("submit-crpa", "--resubmit", ok=True)
        self.assertEqual(self.data()["calls"][1]["args"], ["--parsable", "job.sh"])

    def test_batch_preparation_failure_cannot_be_reported_as_success_on_retry(self):
        marker = self.root / "preparation-fails"
        marker.touch()
        self.assertNotEqual(self.batch().returncode, 0)
        marker.unlink()
        retry = self.batch()
        self.assertNotEqual(retry.returncode, 0, retry.stdout + retry.stderr)
        self.assertIn("failed=1", retry.stdout)
        self.assertEqual(self.data()["calls"], [])
        result = self.batch("--force")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(self.data()["calls"]), 4)
        self.assertEqual(self.batch().returncode, 0)
        self.assertNotEqual(self.batch("--force").returncode, 0)
        self.assertEqual(len(self.data()["calls"]), 4)

    def test_batch_partial_submission_requires_case_recovery(self):
        (self.root / "reject").write_text("02_dos")
        self.assertNotEqual(self.batch().returncode, 0)
        self.assertNotEqual(self.batch().returncode, 0)
        self.assertNotEqual(self.batch("--force").returncode, 0)
        self.assertEqual(len(self.data()["calls"]), 2)


if __name__ == "__main__":
    unittest.main()
