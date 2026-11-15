#!/usr/bin/env python3
"""Process-level regressions for diff-scale's resource measurement."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('diff_scale', ROOT / 'tools/diff-scale-test.py')
scale = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scale)


class MeasurementTest(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / 'target/tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix='measurement-', dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        home = self.work / 'home'
        home.mkdir()
        environment = patch.dict(os.environ, HOME=str(home), SHELL='/bin/sh', TMPDIR=str(self.work))
        environment.start()
        self.addCleanup(environment.stop)

    def test_small_child_does_not_inherit_python_high_water(self):
        held = bytearray(128 * 1024 * 1024)
        for offset in range(0, len(held), 4096):
            held[offset] = 1
        measurement = scale.Measurement(ROOT, self.work, 10)
        result = measurement.run('/bin/true', [], self.work)
        self.assertEqual(result['status'], 0)
        self.assertFalse(result['ended'])
        self.assertLess(result['maxrss_kib'], 32 * 1024, result)
        self.assertEqual(len(held), 128 * 1024 * 1024)

    def test_output_and_nonzero_exit_are_preserved(self):
        measurement = scale.Measurement(ROOT, self.work, 10)
        code = 'import os; os.write(1, b"o"*200000); os.write(2, b"e"*200000); raise SystemExit(7)'
        result = measurement.run(sys.executable, ['-I', '-c', code], self.work)
        self.assertEqual(result['status'], 7)
        self.assertEqual(bytes.fromhex(result['stdout']), b'o' * 200000)
        self.assertEqual(bytes.fromhex(result['stderr']), b'e' * 200000)
        self.assertFalse(result['ended'])
        self.assertGreaterEqual(result['cpu'], 0)
        self.assertGreaterEqual(result['wall'], 0)

    def test_legacy_five_field_report_is_unchanged(self):
        measurement = scale.Measurement(ROOT, self.work, 10)
        report = self.work / 'legacy-usage'
        subprocess.run([str(measurement.parent), str(report), sys.executable, '-I', '-c',
                        'print("legacy output"); raise SystemExit(7)'],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        fields = report.read_text().split()
        self.assertEqual(len(fields), 5)
        self.assertEqual(fields[0], '7')

    def test_invalid_deadlines_never_start_the_command(self):
        measurement = scale.Measurement(ROOT, self.work, 10)
        for timeout in ['nan', 'inf', '0', '-1', '86401', 'not-a-number']:
            with self.subTest(timeout=timeout):
                report = self.work / 'invalid-usage'
                result = subprocess.run([str(measurement.parent), '--timeout', timeout,
                                         str(report), '/bin/true'])
                self.assertEqual(result.returncode, 64)
                self.assertFalse(report.exists())

    def test_deadline_reaps_the_timed_command(self):
        measurement = scale.Measurement(ROOT, self.work, 0.15)
        result = measurement.run(sys.executable, ['-I', '-c', 'import time; time.sleep(30)'], self.work)
        self.assertEqual(result['status'], -9)
        self.assertTrue(result['ended'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
