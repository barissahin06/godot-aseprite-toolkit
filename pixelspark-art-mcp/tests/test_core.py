from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pixelspark_art_mcp.core import generate_scene, validate_manifest


class RigTests(unittest.TestCase):
    def test_manifest_and_scene_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "our-game"
            texture = project / "assets" / "art" / "hero.png"
            texture.parent.mkdir(parents=True)
            texture.write_bytes(b"placeholder")
            manifest = {
                "version": 1,
                "asset_id": "hero",
                "bones": [
                    {"name": "root", "parent": None, "position": [0, 0], "length": 16},
                    {"name": "torso", "parent": "root", "position": [0, -8], "length": 18},
                ],
                "parts": [
                    {"name": "body", "bone": "torso", "texture": "res://assets/art/hero.png"}
                ],
            }
            validate_manifest(manifest, project)
            output = generate_scene(manifest, project / "generated" / "hero.tscn", project)
            text = output.read_text(encoding="utf-8")
            self.assertIn('[node name="Skeleton2D" type="Skeleton2D" parent="."]', text)
            self.assertIn('[node name="torso" type="Bone2D" parent="Skeleton2D/root"]', text)
            self.assertIn('ExtResource("tex_1")', text)

    def test_rejects_missing_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest = {
                "version": 1,
                "asset_id": "hero",
                "bones": [{"name": "root", "parent": "missing"}],
                "parts": [],
            }
            with self.assertRaisesRegex(ValueError, "missing parent"):
                validate_manifest(manifest, Path(temp) / "our-game")


if __name__ == "__main__":
    unittest.main()
