"""Guard owner-approved Qwen and PPS-005 MiniMax R4 model selection.

Static checks only: no downloads, GPU inference or runtime approval.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import model_sync


class OwnerMasterModelSelection(unittest.TestCase):
    def test_qwen_image_weights_remain_exact(self):
        entries = model_sync.select_entries("image")
        self.assertEqual([e[1] for e in entries], [
            "diffusion_models/qwen_image_2.1_bf16.safetensors",
            "text_encoders/qwen3vl_8b_bf16.safetensors",
            "vae/qwen_image_2.1_vae_bf16.safetensors",
        ])

    def test_minimax_default_is_hybrid_and_has_native_audio_vae(self):
        with patch.dict(os.environ, {"PP_VIDEO_VARIANT": "hybrid"}):
            entries = model_sync.select_entries("video")
        selected = {e[1] for e in entries}
        self.assertEqual(len(selected), 4)
        self.assertEqual(selected, {
            "diffusion_models/minimax_h3_hybrid_fl2va_ref2va_b40-49_bf16.safetensors",
            "text_encoders/qwen3vl_32b_minimax_h3_bf16.safetensors",
            "vae/minimax_h3_video_vae_fp16.safetensors",
            "vae/minimax_h3_audio_vae_fp32.safetensors",
        })
        hybrid = next(e for e in entries if e[0] == "video_hybrid")
        self.assertEqual(hybrid[3], "minimax_h3_hybrid_fl2va_ref2va_b40-49_bf16.safetensors")
        self.assertEqual(model_sync.REPOS["video_hybrid"][0],
                         "diobrando0/MiniMax-H3-fl2va-ref2va-hybrids-bf16")

    def test_legacy_is_opt_in_and_never_replaces_hybrid_implicitly(self):
        with patch.dict(os.environ, {"PP_VIDEO_VARIANT": "legacy"}):
            legacy = model_sync.select_entries("video")
        self.assertEqual(len(legacy), 4)
        self.assertIn("diffusion_models/minimax_h3_fl2va_bf16.safetensors",
                      {x[1] for x in legacy})
        with patch.dict(os.environ, {"PP_VIDEO_VARIANT": "both"}):
            both = model_sync.select_entries("both")
        self.assertEqual(len(both), 8)
        with patch.dict(os.environ, {"PP_VIDEO_VARIANT": "unknown"}):
            with self.assertRaisesRegex(ValueError, "PP_VIDEO_VARIANT"):
                model_sync.select_entries("video")

    def test_default_both_covers_all_qwen_and_hybrid_requirements(self):
        with patch.dict(os.environ, {"PP_VIDEO_VARIANT": "hybrid"}):
            both = model_sync.select_entries("both")
        self.assertEqual(len(both), 7)
        self.assertEqual(len({e[1] for e in both}), 7)


if __name__ == "__main__":
    unittest.main()
