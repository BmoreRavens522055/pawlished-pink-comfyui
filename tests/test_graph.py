import copy, json, unittest
from pathlib import Path
from graph_check import check, native_audio_path

SCHEMA = json.loads((Path(__file__).parent / "fixtures/object_info.json").read_text())


class SchemaTests(unittest.TestCase):
    def test_real_multireference_and_audio_sockets(self):
        ref = SCHEMA["MiniMaxH3ReferenceToVideo"]
        self.assertEqual(ref["input"]["optional"]["ref_images"][0], "COMFY_AUTOGROW_V3")
        self.assertEqual(SCHEMA["VAEDecodeAudio"]["output"], ["AUDIO"])
        self.assertEqual(
            SCHEMA["CreateVideo"]["input"]["optional"]["audio"][0], "AUDIO"
        )

    def graph(self):
        return {
            "latent": {
                "class_type": "EmptyMiniMaxH3LatentAV",
                "inputs": {"width": 768, "height": 1344, "length": 124},
            },
            "vae": {
                "class_type": "VAELoader",
                "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"},
            },
            "audio": {
                "class_type": "VAEDecodeAudio",
                "inputs": {"samples": ["latent", 0], "vae": ["vae", 0]},
            },
            "picture": {"class_type": "LoadImage", "inputs": {"image": "approved.png"}},
            "video": {
                "class_type": "CreateVideo",
                "inputs": {"images": ["picture", 0], "fps": 24, "audio": ["audio", 0]},
            },
        }

    def test_audio_connected_and_wrong_type_rejected(self):
        g = self.graph()
        self.assertTrue(native_audio_path(g))
        self.assertEqual(
            check(g, SCHEMA), ["vae.vae_name: value absent from current options"]
        )  # Real fixture has no model weights; do not invent model availability.
        g["video"]["inputs"]["audio"] = ["picture", 0]
        self.assertFalse(native_audio_path(g))
        self.assertTrue(any("cannot connect" in e for e in check(g, SCHEMA)))

    def test_missing_class_index_and_required(self):
        g = self.graph()
        g["audio"]["inputs"]["samples"] = ["latent", 99]
        del g["video"]["inputs"]["fps"]
        g["vae"]["class_type"] = "ImaginaryVAE"
        errors = check(g, SCHEMA)
        self.assertTrue(any("invalid output" in x for x in errors))
        self.assertTrue(any("required" in x for x in errors))
        self.assertTrue(any("unknown class" in x for x in errors))

    def test_real_flat_autogrow_reference_socket(self):
        g = {
            "image": {"class_type": "LoadImage", "inputs": {"image": "approved.png"}},
            "reference": {
                "class_type": "MiniMaxH3ReferenceToVideo",
                "inputs": {
                    "prompt": "approved",
                    "width": 768,
                    "height": 1344,
                    "length": 124,
                    "ref_image_size": "match",
                    "ref_images.ref_image_0": ["image", 0],
                },
            },
        }
        errors = check(g, SCHEMA)
        self.assertEqual(errors, ["reference.clip: required input absent"])
        g["reference"]["inputs"]["ref_images.ref_image_0"] = ["image", 1]
        self.assertTrue(
            any("MASK cannot connect to IMAGE" in e for e in check(g, SCHEMA))
        )
