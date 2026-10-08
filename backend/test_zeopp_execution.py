"""Exercise process cleanup and durable diagnostics with real child processes."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from . import services_zeopp as service


class ZeoppExecutionTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.job_dir = Path(folder.name)
        self.input_path = self.job_dir / 'input.cif'
        self.input_path.write_text('test fixture', encoding='utf-8')
        self.output_path = self.job_dir / 'res.out'

    def metadata(self):
        return json.loads((self.job_dir / 'zeopp-run.json').read_text(encoding='utf-8'))

    def run_engine(self, script, timeout='5'):
        command = [sys.executable, '-u', '-c', script, str(self.output_path)]
        with (
            patch.dict(os.environ, {'CHEMEX_ZEOPP_TIMEOUT_SECONDS': timeout}),
            patch.object(service, 'detect_zeopp_binary', return_value=(Path(sys.executable), 'ready')),
            patch.object(service, 'build_command', return_value=(command, self.output_path, False)),
        ):
            return service.run_workflow(
                'test-job', self.job_dir, self.input_path, 'res', {'numSamples': '100000'},
                lambda *_: None, lambda: 0,
            )

    def test_default_deadline_and_configuration_validation(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(service.get_zeopp_timeout_seconds(), 1800)
        for value in ('0', '-1', 'nan', 'inf', 'invalid', ''):
            with self.subTest(value=value), patch.dict(os.environ, {'CHEMEX_ZEOPP_TIMEOUT_SECONDS': value}):
                with self.assertRaisesRegex(ValueError, 'finite positive'):
                    service.get_zeopp_timeout_seconds()

    def test_success_preserves_output_and_execution_metadata(self):
        result = self.run_engine(
            "import sys; from pathlib import Path; "
            "print('engine output'); print('engine diagnostic', file=sys.stderr); "
            "Path(sys.argv[1]).write_text('input.cif 10 8 9')"
        )
        self.assertEqual(result['returnCode'], 0)
        self.assertEqual(result['metrics'][0]['value'], 10)
        self.assertEqual(len(result['artifacts']), 4)
        for name in ('stdout', 'stderr'):
            self.assertEqual(result[name], (self.job_dir / f'zeopp-{name}.log').read_text())
        metadata = self.metadata()
        self.assertEqual(metadata['status'], 'completed')
        self.assertEqual(metadata['params']['numSamples'], '100000')
        self.assertEqual(metadata['timeoutSeconds'], 5)
        self.assertEqual(metadata['returnCode'], 0)
        self.assertIsNone(metadata['error'])
        self.assertGreater(metadata['elapsedSeconds'], 0)

    def test_timeout_kills_engine_and_preserves_partial_logs(self):
        started = time.monotonic()
        with self.assertRaisesRegex(TimeoutError, 'timed out after 1 seconds'):
            self.run_engine(
                "import sys,time; print('partial output'); "
                "print('partial diagnostic', file=sys.stderr); time.sleep(30)", '1',
            )
        self.assertLess(time.monotonic() - started, 10)
        metadata = self.metadata()
        self.assertEqual(metadata['status'], 'timed_out')
        self.assertIsNotNone(metadata['returnCode'])
        self.assertNotEqual(metadata['returnCode'], 0)
        self.assertIn('timed out', metadata['error'])
        self.assertIn('partial output', (self.job_dir / 'zeopp-stdout.log').read_text())
        self.assertIn('partial diagnostic', (self.job_dir / 'zeopp-stderr.log').read_text())

    def test_logs_are_visible_while_engine_is_running(self):
        release = self.job_dir / 'release'
        failures = []

        def worker():
            try:
                self.run_engine(
                    "import sys,time; from pathlib import Path; print('live output'); "
                    "print('live diagnostic', file=sys.stderr)\n"
                    "while not Path(sys.argv[1]).with_name('release').exists(): time.sleep(0.01)\n"
                    "Path(sys.argv[1]).write_text('input.cif 10 8 9')"
                )
            except Exception as exc:
                failures.append(exc)

        thread = threading.Thread(target=worker)
        thread.start()
        try:
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                logs = [self.job_dir / f'zeopp-{name}.log' for name in ('stdout', 'stderr')]
                if all(p.exists() and p.stat().st_size for p in logs):
                    break
                time.sleep(0.02)
            self.assertTrue(thread.is_alive())
            self.assertEqual(self.metadata()['status'], 'running')
            self.assertIn('live output', logs[0].read_text())
            self.assertIn('live diagnostic', logs[1].read_text())
        finally:
            release.touch()
            thread.join(timeout=10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])

    def test_nonzero_exit_keeps_error_details(self):
        with self.assertRaisesRegex(RuntimeError, 'exit code 7'):
            self.run_engine("import sys; print('invalid structure', file=sys.stderr); sys.exit(7)")
        self.assertEqual(self.metadata()['status'], 'failed')
        self.assertEqual(self.metadata()['returnCode'], 7)
        self.assertIn('invalid structure', (self.job_dir / 'zeopp-stderr.log').read_text())

    def test_parse_failure_keeps_logs_and_metadata(self):
        with self.assertRaisesRegex(ValueError, 'Unexpected ZEO'):
            self.run_engine("import sys; from pathlib import Path; print('finished'); Path(sys.argv[1]).write_text('bad output')")
        self.assertEqual(self.metadata()['status'], 'failed')
        self.assertEqual(self.metadata()['returnCode'], 0)
        self.assertIn('Unexpected', self.metadata()['error'])
        self.assertIn('finished', (self.job_dir / 'zeopp-stdout.log').read_text())

    def test_empty_output_is_an_explicit_failure(self):
        with self.assertRaisesRegex(RuntimeError, 'non-empty output file'):
            self.run_engine('pass')
        self.assertEqual(self.metadata()['status'], 'failed')

    def test_nonzero_exit_with_valid_output_remains_a_warning(self):
        result = self.run_engine("import sys; from pathlib import Path; Path(sys.argv[1]).write_text('input.cif 10 8 9'); sys.exit(3)")
        self.assertIn('exit code 3', result['warning'])
        self.assertEqual(self.metadata()['status'], 'completed')

    def test_launch_failure_is_recorded(self):
        with patch.object(service.subprocess, 'Popen', side_effect=OSError('cannot launch engine')):
            with self.assertRaisesRegex(OSError, 'cannot launch engine'):
                self.run_engine('pass')
        self.assertEqual(self.metadata()['status'], 'failed')
        self.assertIsNone(self.metadata()['returnCode'])
        self.assertIn('cannot launch engine', self.metadata()['error'])


if __name__ == '__main__':
    unittest.main()
