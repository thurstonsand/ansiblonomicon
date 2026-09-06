import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "sanoid_run", Path(__file__).with_name("sanoid-run.py")
)
assert spec is not None and spec.loader is not None
sanoid_run = importlib.util.module_from_spec(spec)
with patch.object(
    sys, "path", [str(Path(__file__).resolve().parents[1] / "maintenance"), *sys.path]
):
    spec.loader.exec_module(sanoid_run)


class SanoidRunTest(unittest.TestCase):
    def test_exit_status_and_stderr(self):
        for status, stderr, expected in (
            (0, b"", 0),
            (0, b"WARNING: cannot create snapshot\n", 1),
            (7, b"", 7),
            (7, b"cannot destroy snapshot\n", 7),
        ):
            with self.subTest(status=status, stderr=stderr):
                output = io.BytesIO()
                result = subprocess.CompletedProcess([], status, stderr=stderr)
                with (
                    patch.object(sanoid_run, "verify_datasets"),
                    patch.object(
                        sanoid_run.subprocess, "run", return_value=result
                    ) as run,
                    patch.object(sys, "stderr", io.TextIOWrapper(output)),
                ):
                    self.assertEqual(
                        sanoid_run.main(["--take-snapshots", "--verbose"]), expected
                    )
                    self.assertEqual(output.getvalue(), stderr)
                run.assert_called_once_with(
                    ["/usr/sbin/sanoid", "--take-snapshots", "--verbose"],
                    stderr=subprocess.PIPE,
                )

    def test_verified_roots_and_children(self):
        properties = (
            "org.ansiblonomicon:layout\tfresh-v1\tlocal\n"
            "org.ansiblonomicon:migration\tverified\tlocal\n"
        )
        results = [
            subprocess.CompletedProcess([], 0, stdout=sanoid_run.POOLS["black-box"]),
            subprocess.CompletedProcess([], 0, stdout=properties * 3),
            subprocess.CompletedProcess([], 0, stdout=properties * 2),
        ]
        with patch.object(sanoid_run.subprocess, "run", side_effect=results) as run:
            sanoid_run.verify_datasets()
        self.assertEqual(run.call_args_list[0].args[0][-1], "black-box")
        self.assertEqual(run.call_args_list[1].args[0][-1], "black-box/docker")
        self.assertEqual(run.call_args_list[2].args[0][-1], "black-box/agents")
        self.assertEqual(run.call_count, 3)

    def test_unverified_tree_never_runs_sanoid(self):
        properties = (
            "org.ansiblonomicon:layout\tfresh-v1\tlocal\n"
            "org.ansiblonomicon:migration\tverified\tlocal\n"
        )
        for invalid in (
            "",
            properties.replace("verified", "pending"),
            properties.replace("local", "inherited from black-box"),
            properties + "org.ansiblonomicon:migration\t-\t-\n",
            properties.splitlines()[0] + "\n",
        ):
            for failed_root in (0, 1):
                with self.subTest(invalid=invalid, failed_root=failed_root):
                    results = [
                        subprocess.CompletedProcess(
                            [], 0, stdout=sanoid_run.POOLS["black-box"]
                        ),
                        *[
                            subprocess.CompletedProcess([], 0, stdout=properties)
                            for _ in range(failed_root)
                        ],
                        subprocess.CompletedProcess([], 0, stdout=invalid),
                    ]
                    with (
                        patch.object(
                            sanoid_run.subprocess, "run", side_effect=results
                        ) as run,
                        self.assertRaises(ValueError),
                    ):
                        sanoid_run.main(["--prune-snapshots", "--verbose"])
                    self.assertEqual(run.call_count, failed_root + 2)

    def test_wrong_pool_never_runs_sanoid(self):
        result = subprocess.CompletedProcess([], 0, stdout="wrong-guid\n")
        with (
            patch.object(sanoid_run.subprocess, "run", return_value=result) as run,
            self.assertRaises(ValueError),
        ):
            sanoid_run.main(["--take-snapshots", "--verbose"])
        self.assertEqual(run.call_count, 1)

    def test_zfs_query_failure_never_runs_sanoid(self):
        results = [
            subprocess.CompletedProcess([], 0, stdout=sanoid_run.POOLS["black-box"]),
            subprocess.CalledProcessError(1, ["/usr/sbin/zfs", "get"]),
        ]
        with (
            patch.object(sanoid_run.subprocess, "run", side_effect=results) as run,
            self.assertRaises(subprocess.CalledProcessError),
        ):
            sanoid_run.main(["--take-snapshots", "--verbose"])
        self.assertEqual(run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
