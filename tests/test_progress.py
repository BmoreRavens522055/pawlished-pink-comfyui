"""Exercise actual pinned HF Xet reporting adapter, including compression counters."""

import json, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from hf_worker import progress_class
from huggingface_hub.utils._xet_progress_reporting import XetDownloadProgressReporter


class NativeProgress(unittest.TestCase):
    def test_reconstruction_and_wire_bytes_are_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "progress.json"
            with XetDownloadProgressReporter(
                reconstruction_desc="file",
                total=8 * 1024**2,
                log_level=20,
                tqdm_class=progress_class(p, "b", "a"),
            ) as reporter:
                reporter.update_progress(
                    SimpleNamespace(
                        total_bytes_completed=4 * 1024**2,
                        total_transfer_bytes_completed=1 * 1024**2,
                        total_bytes_completion_rate=10,
                        total_transfer_bytes_completion_rate=5,
                        total_bytes=8 * 1024**2,
                    )
                )
                j = json.loads(p.read_text())
                self.assertEqual(j["bytes"], 4 * 1024**2)
                self.assertEqual(j["transfer_bytes"], 1 * 1024**2)
                self.assertEqual(j["total"], 8 * 1024**2)
            self.assertEqual(json.loads(p.read_text())["bytes"], 4 * 1024**2)
