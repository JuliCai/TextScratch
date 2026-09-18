import io
import json
import tempfile
import unittest
import wave
import zipfile
from pathlib import Path

from textscratch.assets import copy_costumes, copy_sounds, prepare_costumes, prepare_sounds


class AssetTests(unittest.TestCase):
    def test_large_costume_and_sound_collections_keep_index_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            costumes = root / "costumes"
            sounds = root / "sounds"
            costumes.mkdir()
            sounds.mkdir()
            for i in (0, 1, 10, 99, 100, 999, 1000, 1001):
                (costumes / f"{i:03d}__asset.svg").write_text('<svg width="10" height="20"/>')
                (sounds / f"sound_{i:03d}__asset.wav").write_bytes(b"test")
            cs, _ = prepare_costumes(str(costumes))
            ss, _ = prepare_sounds(str(sounds))
            self.assertEqual([s["name"] for s in ss], [f"sound_{i:03d}__asset" for i in (0, 1, 10, 99, 100, 999, 1000, 1001)])
            self.assertEqual(len(cs), 8)
            self.assertEqual((cs[0]["rotationCenterX"], cs[0]["rotationCenterY"]), (5, 10))

    def test_sound_metadata_and_bytes_survive_extraction(self):
        data = io.BytesIO()
        with wave.open(data, "wb") as audio:
            audio.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
            audio.writeframes(b"\x00\x00" * 2205)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("sound.wav", data.getvalue())
            target = {"sounds": [{"name": "Hello!?", "md5ext": "sound.wav", "rate": 22050, "sampleCount": 2205, "format": ""}]}
            with zipfile.ZipFile(archive) as z:
                copy_sounds(target, z, str(root))
            sounds, files = prepare_sounds(str(root))
            self.assertEqual(sounds[0]["name"], "Hello!?")
            self.assertEqual(sounds[0]["rate"], 22050)
            self.assertEqual(sounds[0]["sampleCount"], 2205)
            self.assertEqual(Path(files[0][0]).read_bytes(), data.getvalue())

    def test_missing_md5ext_and_extra_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = b'<svg width="10" height="20"/>'
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("asset.svg", data)
            target = {"costumes": [{"name": "", "assetId": "asset", "dataFormat": "svg", "rotationCenterX": 7, "rotationCenterY": 8, "bitmapResolution": 1}]}
            with zipfile.ZipFile(archive) as z:
                copy_costumes(target, z, str(root))
            (root / "notes.txt").write_text("not an image")
            (root / "desktop.ini").write_text("not an image")
            costumes, files = prepare_costumes(str(root))
            self.assertEqual(len(costumes), 1)
            self.assertEqual(costumes[0]["name"], "")
            self.assertEqual(costumes[0]["rotationCenterX"], 7)
            self.assertEqual(Path(files[0][0]).read_bytes(), data)
