"""One pinned HF transfer. Progress comes from HF/Xet's payload callback."""

import json
import os
from pathlib import Path
import sys
import time
from pp_common import atomic


def progress_class(event, boot, attempt):
    from tqdm.auto import tqdm

    class Progress(tqdm):
        def __init__(self, *args, **kwargs):
            kwargs["disable"] = False
            self.transfer_bytes = 0
            super().__init__(*args, **kwargs)
            self.emit()

        def emit(self):
            atomic(
                Path(event),
                {
                    "bytes": self.n,
                    "total": self.total,
                    "transfer_bytes": self.transfer_bytes,
                    "updated": time.time(),
                    "boot_id": boot,
                    "attempt": attempt,
                },
            )

        def update(self, n=1):
            result = super().update(n)
            self.emit()
            return result

        # HF 2.2.0 routes its separate Xet transfer counter through these methods.
        # Reconstruction n determines file percentage; compressed wire bytes never do.
        def update_transfer(self, n):
            self.transfer_bytes += n
            self.emit()

        def set_transfer_postfix_str(self, value, refresh=False):
            pass

        def close(self):
            if hasattr(self, "n"):
                self.emit()
            super().close()

    return Progress


def main():
    from huggingface_hub import hf_hub_download

    repo, revision, rel, stage, event, boot, attempt = sys.argv[1:]
    hf_hub_download(
        repo_id=repo,
        filename=rel,
        revision=revision,
        local_dir=stage,
        tqdm_class=progress_class(event, boot, attempt),
    )


if __name__ == "__main__":
    main()
