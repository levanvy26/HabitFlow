# -*- coding: utf-8 -*-
"""
DATA-01 tests: atomic save in app.Api.save_data.
Run:  python -m unittest tests.test_atomic_save -v   (from d:\\HabitFlow)
All tests use a temp directory; the real habit_data.json is never touched.
Faults are SIMULATED via mocks, not real crashes / power loss.
"""
import os
import sys
import json
import glob
import shutil
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app  # noqa: E402

OLD = {"habits": [{"id": "h1", "name": "Đọc sách"}], "categories": [], "logs": {}, "settings": {"theme": "dark"}}
NEW = {"habits": [{"id": "h2", "name": "Chạy bộ"}], "categories": [], "logs": {"2026-01-01": {"h2": True}}, "settings": {"theme": "light"}}


class AtomicSaveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hf_test_")
        self.target = os.path.join(self.tmp, "habit_data.json")
        with open(self.target, "w", encoding="utf-8") as f:
            json.dump(OLD, f, ensure_ascii=False)
        self.patcher = mock.patch.object(app, "DATA_FILE", self.target)
        self.patcher.start()
        self.api = app.Api()

    def tearDown(self):
        self.patcher.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _read(self):
        with open(self.target, "r", encoding="utf-8") as f:
            return json.load(f)

    def _leftover_tmp(self):
        return glob.glob(os.path.join(self.tmp, ".habit_data.*.tmp"))

    def test_1_valid_save_roundtrip(self):
        res = self.api.save_data(NEW)
        self.assertEqual(res["status"], "ok")
        self.assertEqual(self._read(), NEW)
        self.assertEqual(self._leftover_tmp(), [])

    def test_1b_string_payload_still_supported(self):
        res = self.api.save_data(json.dumps(NEW, ensure_ascii=False))
        self.assertEqual(res["status"], "ok")
        self.assertEqual(self._read(), NEW)

    def test_2_failure_while_writing_temp_keeps_old_file(self):
        with mock.patch.object(app.os, "fsync", side_effect=OSError("simulated disk error")):
            res = self.api.save_data(NEW)
        self.assertEqual(res["status"], "error")
        self.assertIn("simulated disk error", res["message"])
        self.assertEqual(self._read(), OLD)
        self.assertEqual(self._leftover_tmp(), [])

    def test_3_failure_on_replace_returns_error_and_keeps_old_file(self):
        with mock.patch.object(app.os, "replace", side_effect=PermissionError("simulated lock")):
            res = self.api.save_data(NEW)
        self.assertEqual(res["status"], "error")
        self.assertTrue(os.path.exists(self.target))
        self.assertEqual(self._read(), OLD)
        self.assertEqual(self._leftover_tmp(), [])

    def test_3b_unserializable_data_never_touches_target(self):
        res = self.api.save_data({"bad": {1, 2, 3}})  # set is not JSON serializable
        self.assertEqual(res["status"], "error")
        self.assertEqual(self._read(), OLD)
        self.assertEqual(self._leftover_tmp(), [])

    def test_5_concurrent_saves_leave_valid_json(self):
        payloads = [{"habits": [], "categories": [], "logs": {}, "settings": {"n": i}} for i in range(40)]
        errors = []

        def worker(p):
            r = self.api.save_data(p)
            if r["status"] != "ok":
                errors.append(r)

        threads = [threading.Thread(target=worker, args=(p,)) for p in payloads]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(errors, [])
        final = self._read()  # must parse
        self.assertIn(final, payloads)  # last writer wins; order is NOT guaranteed
        self.assertEqual(self._leftover_tmp(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)

