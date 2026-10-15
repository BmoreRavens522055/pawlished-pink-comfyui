import contextlib, io, json, os, struct, subprocess, sys, tempfile, time, unittest, zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pp_common as common
import model_sync as models
import episode, pp_runtime, ppctl


def tensor(path):
    header = json.dumps(
        {"x": {"dtype": "U8", "shape": [4], "data_offsets": [0, 4]}},
        separators=(",", ":"),
    ).encode()
    header += b" " * ((-len(header)) % 8)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(struct.pack("<Q", len(header)) + header + b"1234")
    return path.stat().st_size


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.setup = self.root / "PP_RunPod_Setup"
        self.patches = []
        for module in [common, models, episode, pp_runtime, ppctl]:
            for key, value in [("ROOT", self.root), ("SETUP", self.setup)]:
                p = patch.object(module, key, value)
                p.start()
                self.patches.append(p)
        self.env = patch.dict(
            os.environ,
            {
                "PP_MODE": "image",
                "PP_STORAGE_REVIEWED": "1",
                "JUPYTER_PASSWORD": "test-only-auth",
                "PP_DOWNLOAD_WORKERS": "1",
            },
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_auth_prevents_launch(self):
        for env in [{"JUPYTER_PASSWORD": ""}, {"JUPYTER_DISABLE_AUTH": "TRUE"}]:
            with self.subTest(env=env), patch.dict(os.environ, env), patch.object(
                pp_runtime.Supervisor, "launch"
            ) as launch:
                self.assertEqual(pp_runtime.Supervisor().run(), 1)
                launch.assert_not_called()
                self.assertEqual(
                    common.read(self.setup / "startup_state.json")["phase"], "FAILED"
                )

    def test_storage_and_paths(self):
        with patch.dict(os.environ, {"PP_STORAGE_REVIEWED": "0"}):
            with self.assertRaises(ValueError):
                pp_runtime.Supervisor().preflight()
        s = pp_runtime.Supervisor()
        s.preflight()
        self.assertEqual(
            s.state["storage"], "DECLARED_PERSISTENT_NOT_PROVIDER_VERIFIED"
        )
        for kind in ("input", "output", "temp", "user"):
            self.assertTrue((self.root / "ComfyUI" / kind).is_dir())

    def test_state_freshness(self):
        s = {"boot_id": "old", "updated": time.time()}
        self.assertFalse(common.fresh(s, "new"))
        self.assertTrue(common.fresh(s, "old"))
        s["updated"] -= 60
        self.assertFalse(common.fresh(s, "old"))

    def test_existing_downloads_disabled(self):
        size = tensor(self.root / "models/vae/a.safetensors")
        models.run(
            "image", "b", False, [("image", "vae/a.safetensors", size)], poll=0.01
        )
        self.assertEqual(
            common.read(self.setup / "model_state.json")["phase"],
            "VERIFIED_BYTES_OPENABLE",
        )

    def test_same_size_garbage(self):
        p = self.root / "models/vae/a.safetensors"
        size = tensor(p)
        p.write_bytes(b"x" * size)
        with self.assertRaises(Exception):
            models.run(
                "image", "b", False, [("image", "vae/a.safetensors", size)], poll=0.01
            )
        self.assertEqual(p.read_bytes(), b"x" * size)
        self.assertEqual(
            common.read(self.setup / "model_state.json")["phase"], "FAILED"
        )

    def test_missing_disabled(self):
        with self.assertRaisesRegex(RuntimeError, "disabled"):
            models.run("image", "b", False, [("image", "vae/a", 100)])

    def test_insufficient_memory_disk(self):
        from collections import namedtuple

        for memory, free, message in [(1, 10**12, "RAM"), (30 * common.GIB, 1, "disk")]:
            with patch.object(
                models, "memory_available", return_value=memory
            ), patch.object(
                models.shutil,
                "disk_usage",
                return_value=namedtuple("disk", "total used free")(free, 0, free),
            ):
                with self.assertRaisesRegex(RuntimeError, message):
                    models.run("image", "b", True, [("image", "vae/a", 100)])

    def worker(self, body):
        f = self.root / "worker.py"
        f.write_text(
            "import sys,time,json,os\nfrom pathlib import Path\nrepo,rev,rel,stage,event,boot,attempt=sys.argv[1:]\np=Path(stage)/rel;p.parent.mkdir(parents=True,exist_ok=True)\n"
            + body
        )
        return [sys.executable, str(f)]

    def run_worker(self, command, **kwargs):
        size = tensor(self.root / "source.safetensors")
        with patch.object(models, "memory_available", return_value=30 * common.GIB):
            models.run(
                "image",
                "b",
                True,
                [("image", "vae/a.safetensors", size)],
                command,
                reserve=0,
                poll=0.02,
                **kwargs,
            )

    def test_measured_transfer(self):
        p = self.root / "source.safetensors"
        size = tensor(p)
        command = self.worker(
            f"data=Path({str(p)!r}).read_bytes()\nfor n in range(0,len(data)+1,8):\n p.write_bytes(data[:n]);Path(event).write_text(json.dumps(dict(bytes=n,total=len(data),boot_id=boot,attempt=attempt)));time.sleep(.03)\np.write_bytes(data)\n"
        )
        self.run_worker(command)
        self.assertEqual(
            common.read(self.setup / "model_state.json")["files"]["vae/a.safetensors"][
                "bytes"
            ],
            size,
        )
        self.assertEqual(
            (self.root / "models/vae/a.safetensors").read_bytes(), p.read_bytes()
        )

    def test_exit_minus9_resume(self):
        command = self.worker('p.write_bytes(b"partial");os.kill(os.getpid(),9)\n')
        with self.assertRaisesRegex(RuntimeError, "exit -9"):
            self.run_worker(command)
        command = self.worker(
            f'assert p.read_bytes()==b"partial"\np.write_bytes(Path({str(self.root/"source.safetensors")!r}).read_bytes())\n'
        )
        self.run_worker(command)

    def test_stall_and_deadline(self):
        for kw in [dict(stall=0.1), dict(deadline=0.1)]:
            start = time.monotonic()
            with self.assertRaises(TimeoutError):
                self.run_worker(self.worker("time.sleep(30)\n"), **kw)
            self.assertLess(time.monotonic() - start, 3)

    def test_cgroup_budget(self):
        c = self.root / "cg"
        c.mkdir()
        (c / "memory.max").write_text("100")
        (c / "memory.current").write_text("70")
        self.assertEqual(common.memory_available(c), 30)

    def archive(self, entries):
        p = self.root / "episode.zip"
        with zipfile.ZipFile(p, "w") as z:
            for name, data in entries:
                z.writestr(name, data)
        return p

    def test_episode_root_repeat_conflict(self):
        p = self.archive(
            [
                ("PPS-009/Pics/BEFORE.PNG", b"approved"),
                ("PPS-009/JSON/Cloud/shot.json", b"{}"),
            ]
        )
        dest = self.root / "input"
        self.assertEqual(episode.ingest(p, dest), "PPS-009")
        self.assertTrue(
            (dest / "PPS-009/Blueprint & Shot Prompts/Audio Execution").is_dir()
        )
        self.assertEqual(episode.ingest(p, dest), "PPS-009")
        (dest / "PPS-009/Pics/BEFORE.PNG").write_bytes(b"accepted repair")
        with self.assertRaisesRegex(ValueError, "conflict"):
            episode.ingest(p, dest)
        self.assertEqual(
            (dest / "PPS-009/Pics/BEFORE.PNG").read_bytes(), b"accepted repair"
        )

    def test_unsafe_archives_transactional(self):
        for entries in [
            [("../escape", b"x")],
            [("/absolute", b"x")],
            [("PPS/a", b"x"), ("OTHER/b", b"x")],
            [("PPS/a", b"x"), ("PPS/a", b"y")],
            [("PPS/../a", b"x")],
            [("PPS/C:\\x", b"x")],
            [("PPS/a", b"x"), ("PPS/a/b", b"x")],
        ]:
            with self.subTest(entries=entries), self.assertRaises(
                (ValueError, OSError)
            ):
                episode.ingest(self.archive(entries), self.root / "in")
            self.assertFalse((self.root / "in/PPS").exists())

    def test_zip_symlink(self):
        p = self.root / "symlink.zip"
        with zipfile.ZipFile(p, "w") as z:
            i = zipfile.ZipInfo("PPS/link")
            i.create_system = 3
            i.external_attr = 0o120777 << 16
            z.writestr(i, "../../secret")
        with self.assertRaises(ValueError):
            episode.ingest(p, self.root / "in")

    def test_monitor_read_only_stale(self):
        self.setup.mkdir()
        common.atomic(
            self.setup / "startup_state.json",
            {"boot_id": "b", "updated": 0, "phase": "READY"},
        )
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with contextlib.redirect_stdout(io.StringIO()) as out:
            ppctl.display()
        self.assertIn("STALE", out.getvalue())
        self.assertEqual(
            before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        )

    def test_retrieval_crc_outputs(self):
        p = self.root / "ComfyUI/output/accepted.txt"
        p.parent.mkdir(parents=True)
        p.write_text("accepted")
        archive = episode.snapshot("boot")
        with zipfile.ZipFile(archive) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(z.read("ComfyUI/output/accepted.txt"), b"accepted")

    def test_service_start_deadline_cleans_processes(self):
        supervisor = pp_runtime.Supervisor()
        real_launch = supervisor.launch

        def sleeping(name, cmd, env=None, cwd=None):
            return real_launch(
                name, [sys.executable, "-c", "import time;time.sleep(60)"]
            )

        with patch.object(supervisor, "launch", side_effect=sleeping), patch.dict(
            os.environ,
            {"PP_SERVICE_TIMEOUT": "1", "PP_JUPYTER_PORT": "1", "PP_COMFY_PORT": "2"},
        ):
            start = time.monotonic()
            self.assertEqual(supervisor.run(), 1)
            self.assertLess(time.monotonic() - start, 5)
            self.assertTrue(
                all(p.poll() is not None for p in supervisor.children.values())
            )
            self.assertIn(
                "wall-clock", common.read(self.setup / "startup_state.json")["error"]
            )

    def test_corrupt_zip_crc_does_not_commit_episode(self):
        p = self.archive([("PPS/Pics/a.txt", b"UNIQUE_PAYLOAD")])
        data = p.read_bytes()
        p.write_bytes(data.replace(b"UNIQUE_PAYLOAD", b"BROKEN_PAYLOAD", 1))
        with self.assertRaises(zipfile.BadZipFile):
            episode.ingest(p, self.root / "in")
        self.assertFalse((self.root / "in/PPS").exists())


if __name__ == "__main__":
    unittest.main()
