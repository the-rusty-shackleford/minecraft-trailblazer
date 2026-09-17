"""Cosmetic import contract tests using real source projects, PNGs and filesystem exports.

Partitions: cube versus polygon UVs; reversed bounds; invalid/nonfinite UVs;
explicit/missing import mode; unchanged versus altered gameplay contract;
first/repeated export; original opaque atlas pixels; retained rig groups and tyre geometry.
Copyright 2026 Rusty Shackleford and nfx. SPDX-License-Identifier: AGPL-3.0-or-later.
"""

from __future__ import annotations

import base64
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import cast

from appearance import shift_uv, uv_bounds
from PIL import Image

ART = Path(__file__).resolve().parent
ROOT = ART.parents[1]


def model(path: Path) -> dict[str, object]:
    """effects: reads a model object; throws: TypeError for a non-object root."""
    value: object = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise TypeError("expected a model object")
    return cast(dict[str, object], value)


def elements(value: dict[str, object]) -> dict[str, dict[str, object]]:
    """requires: a Blockbench model; effects: indexes elements by UUID."""
    return {str(e["uuid"]): e for e in cast(list[dict[str, object]], value["elements"])}


def texture(value: dict[str, object]) -> Image.Image:
    """requires: an embedded PNG atlas; effects: decodes its original RGBA pixels."""
    tex = cast(list[dict[str, object]], value["textures"])[0]
    png = base64.b64decode(str(tex["source"]).split(",", 1)[1])
    return Image.open(io.BytesIO(png)).convert("RGBA")


class AppearanceTest(unittest.TestCase):
    """AF: each test observes one import boundary; RI: repository inputs are never written."""

    def test_cube_and_polygon_coordinates(self) -> None:
        self.assertEqual(uv_bounds([9, 8, 2, 1]), (2, 1, 9, 8))
        self.assertEqual(shift_uv([9, 8, 2, 1], 4, -1), [13, 7, 6, 0])
        corners = {"a": [1, 4], "b": [7, 2], "c": [3, 8]}
        self.assertEqual(uv_bounds(corners), (1, 2, 7, 8))
        self.assertEqual(
            shift_uv(corners, 2, -1), {"a": [3, 3], "b": [9, 1], "c": [5, 7]}
        )
        self.assertEqual(corners["a"], [1, 4])

    def test_invalid_uvs_rejected(self) -> None:
        for value in [
            [],
            {},
            [1, 2],
            [True, 0, 1, 2],
            [0, 0, float("nan"), 1],
            {"a": [1]},
        ]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                uv_bounds(value)

    def test_source_rig_and_original_texture(self) -> None:
        reference = next((ART / "reference").glob("*-before-cosmetics.bbmodel"))
        current = next((ART / "preview").glob("*.bbmodel"))
        old, new = model(reference), model(current)
        self.assertEqual(
            old["groups"], new["groups"], "rig groups and animation origins"
        )
        before, after = elements(old), elements(new)
        for key, e in before.items():
            name = str(e["name"])
            if name.startswith(("tyre_", "tread_", "wheel_-", "wheel_1")) and (
                "faces" in e
            ):
                self.assertIn(key, after, name)
                for field in ["from", "to", "origin", "rotation", "vertices"]:
                    self.assertEqual(
                        e.get(field), after[key].get(field), name + "/" + field
                    )
            if name.startswith(
                (
                    "needle_",
                    "dial_",
                    "seat_",
                    "headlight_",
                    "lens_",
                    "tail_light_",
                    "rear_reflector_",
                )
            ) or name in {
                "hitch",
                "hitch_ball",
                "tow_coupler",
                "windshield_glass",
                "cab_rear_glass",
                "windshield",
                "rear_door_left",
                "rear_door_right",
                "tailgate",
                "tailgate_rail",
            }:
                self.assertEqual(e, after[key], name)
        old_im, new_im = texture(old), texture(new)
        a = old_im.tobytes()
        b = new_im.crop((0, 0, old_im.width, old_im.height)).tobytes()
        for i in range(0, len(a), 4):
            if a[i + 3]:
                self.assertEqual(
                    a[i : i + 4], b[i : i + 4], f"original atlas pixel {i // 4}"
                )

    def test_real_export_preserves_gameplay_and_is_reproducible(self) -> None:
        import subprocess

        # A fresh filesystem copy exercises the real importer; no backend is mocked.
        with tempfile.TemporaryDirectory(prefix="appearance-") as directory:
            root = Path(directory)
            shutil.copytree(
                ART, root / "devtools/art", ignore=shutil.ignore_patterns("__pycache__")
            )
            shutil.copytree(ROOT / "src/main/resources", root / "src/main/resources")
            resources = root / "src/main/resources"
            protected = {
                p.relative_to(resources): p.read_bytes()
                for p in resources.rglob("*")
                if p.is_file() and ("/data/" in str(p) or "/lang/" in str(p))
            }
            script = "adopt.py" if (ART / "adopt.py").exists() else "build.py"
            command = [sys.executable, str(root / "devtools/art" / script)]
            denied = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertNotEqual(denied.returncode, 0)
            self.assertIn("--appearance-only", denied.stderr)
            outputs = {
                p.relative_to(resources): p.read_bytes()
                for p in resources.rglob("*.bbmodel")
            }
            for _ in range(2):
                result = subprocess.run(
                    [*command, "--appearance-only"], capture_output=True, text=True, check=False
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                for rel, expected in protected.items():
                    self.assertEqual((resources / rel).read_bytes(), expected, str(rel))
                for rel, expected in outputs.items():
                    self.assertEqual((resources / rel).read_bytes(), expected, str(rel))
            profile = next((resources / "data").glob("*/vanillawheels/vehicle/*.json"))
            profile.write_text("{}")
            denied = subprocess.run(
                [*command, "--appearance-only"], capture_output=True, text=True, check=False
            )
            self.assertNotEqual(denied.returncode, 0)
            self.assertIn("Gameplay profile differs", denied.stderr)


if __name__ == "__main__":
    unittest.main()
