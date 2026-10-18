"""Independent IMAGE and VIDEO ZIP intake for one Pawlished & Pink episode.

Synthetic fixtures only; no real episode record, GPU or model download.
"""
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import episode


def package(root, dest, members):
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_STORED) as z:
        for name, data in members.items():
            z.writestr(root + "/" + name, data)
    return dest


class TwoZipIntake(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = "PPS-010"
        self.image = package(self.root, self.base / "01_IMAGE.zip", {
            "JSON/Cloud/SHOT_01_QWEN.api.json": b'{"class_type":"TextEncodeQwenImage21"}',
            "Pics/SHOT_01_QWEN.png": b"accepted-first-frame",
            "Blueprint & Shot Prompts/Image Prompts/SHOT_01.txt": b"image plan",
        })
        self.video = package(self.root, self.base / "02_VIDEO.zip", {
            # VIDEO is self-contained, not dependent on IMAGE ZIP assets:
            "Pics/SHOT_01_QWEN.png": b"accepted-first-frame",
            "Pics/FOH_ROOM.png": b"wide-room-reference",
            "JSON/Cloud/SHOT_01_MINIMAX.api.json": b'{"class_type":"MiniMaxH3ImageAndReferenceToVideo"}',
            "Blueprint & Shot Prompts/Technical Companions/SHOT_01.txt": b"video plan",
        })

    def tearDown(self):
        self.tmp.cleanup()

    def stage(self, first, second):
        dest = self.base / "pod-input"
        self.assertEqual(episode.ingest(first, dest), self.root)
        self.assertEqual(episode.ingest(second, dest), self.root)
        return dest / self.root

    def test_image_then_video_same_episode_root(self):
        root = self.stage(self.image, self.video)
        self.assertEqual((root / "Pics/SHOT_01_QWEN.png").read_bytes(), b"accepted-first-frame")
        self.assertEqual((root / "Pics/FOH_ROOM.png").read_bytes(), b"wide-room-reference")
        self.assertTrue((root / "JSON/Cloud/SHOT_01_QWEN.api.json").is_file())
        self.assertTrue((root / "JSON/Cloud/SHOT_01_MINIMAX.api.json").is_file())
        self.assertTrue((root / "Blueprint & Shot Prompts/Still Generation Dashboard").is_dir())

    def test_video_package_standalone_then_image(self):
        root = self.stage(self.video, self.image)
        self.assertTrue((root / "Pics/SHOT_01_QWEN.png").is_file())
        self.assertTrue((root / "Pics/FOH_ROOM.png").is_file())
        self.assertTrue((root / "JSON/Cloud/SHOT_01_QWEN.api.json").is_file())

    def test_repeated_uploads_do_not_modify_existing_files(self):
        root = self.stage(self.image, self.video)
        frame = root / "Pics/SHOT_01_QWEN.png"
        before = (frame.stat().st_ino, frame.stat().st_size, frame.read_bytes())
        self.assertEqual(episode.ingest(self.video, self.base / "pod-input"), self.root)
        self.assertEqual(episode.ingest(self.image, self.base / "pod-input"), self.root)
        self.assertEqual(before, (frame.stat().st_ino, frame.stat().st_size, frame.read_bytes()))

    def test_conflicting_second_zip_is_rejected_without_overwrite(self):
        dest = self.base / "pod-input"
        episode.ingest(self.image, dest)
        conflict = package(self.root, self.base / "03_CONFLICT.zip", {
            "Pics/NEW_REF.png": b"must-not-be-added",
            "Pics/SHOT_01_QWEN.png": b"wrong-first-frame",
        })
        with self.assertRaisesRegex(ValueError, "existing episode conflict"):
            episode.ingest(conflict, dest)
        root = dest / self.root
        self.assertEqual((root / "Pics/SHOT_01_QWEN.png").read_bytes(), b"accepted-first-frame")
        self.assertFalse((root / "Pics/NEW_REF.png").exists())

    def test_no_existing_episode_deleted_on_corrupt_video_zip(self):
        dest = self.base / "pod-input"
        episode.ingest(self.image, dest)
        raw = self.video.read_bytes()
        self.video.write_bytes(raw.replace(b"wide-room-reference", b"BROKENroom-reference", 1))
        with self.assertRaises(zipfile.BadZipFile):
            episode.ingest(self.video, dest)
        root = dest / self.root
        self.assertEqual((root / "Pics/SHOT_01_QWEN.png").read_bytes(), b"accepted-first-frame")
        self.assertFalse((root / "Pics/FOH_ROOM.png").exists())

    def test_two_zip_uploads_report_one_staged_episode(self):
        upload = self.base / "uploads"
        upload.mkdir()
        (upload / "01_IMAGE.zip").write_bytes(self.image.read_bytes())
        (upload / "02_VIDEO.zip").write_bytes(self.video.read_bytes())
        with patch.object(episode, "ROOT", self.base):
            self.assertEqual(episode.stage_uploads(), [self.root])
        self.assertTrue((self.base / "ComfyUI/input/PPS-010/JSON/Cloud/SHOT_01_MINIMAX.api.json").is_file())


if __name__ == "__main__":
    unittest.main()
