"""Import the approved cosmetic Blockbench derivative without changing gameplay.

Run with --appearance-only. The released profile and original model are retained in
reference/. The profile is checked before import and is never regenerated from artwork.
This preserves nfx's rig and the existing gameplay while allowing deliberate art edits.
Copyright 2026 Rusty Shackleford and nfx. SPDX-License-Identifier: AGPL-3.0-or-later.
"""
from __future__ import annotations

import base64
import json
import struct
import sys
import zlib
from pathlib import Path

from appearance import require_appearance_only, uv_bounds

ROOT = Path(__file__).resolve().parents[2]
MODID = "trailblazer"
ASSETS = ROOT / "src/main/resources/assets" / MODID
DATA = ROOT / "src/main/resources/data" / MODID
PREVIEW = ROOT / "devtools/art/preview/trailblazer.bbmodel"

# The tint the preview's body texels carry: light-blue dye lifted a quarter toward white, as Vanilla Wheels
# paints a dyed vehicle. Dividing it out gives the greys the game multiplies its paint into.
PREVIEW_TINT = (107, 198, 227)
# What an undyed truck wears in the game: the same tint, so the game shows the preview's colour.
FACTORY = "#%02x%02x%02x" % PREVIEW_TINT

WHEEL_GROUP = "wheel_0_left"
CHEST_GROUP = "trunk_chest"
# A rider's attachment point sits this far (mesh units) above the cushion: nfx's placement, found in
# game -- the game puts a player's feet 0.6 blocks under the attachment and the sitting pose the hips
# 12 units over the feet, so the body lands on the cushion; anything more floats the rider.
SEAT_LIFT = 0.4


# ---------------------------------------------------------------- PNG

def read_png(data: bytes):
    pos = 8
    chunks = []
    w = h = ct = 0
    while pos < len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if kind == b"IHDR":
            w, h, _bd, ct = struct.unpack(">IIBB", body[:10])
        elif kind == b"IDAT":
            chunks.append(body)
    raw = zlib.decompress(b"".join(chunks))
    bpp = {2: 3, 6: 4}[ct]
    stride = w * bpp
    rows = []
    prev = bytearray(stride)
    p = 0
    for _ in range(h):
        f = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append([tuple(line[x * bpp:x * bpp + bpp]) + ((255,) if bpp == 3 else ()) for x in range(w)])
        prev = line
    return w, h, rows


def write_png(w: int, h: int, rows) -> bytes:
    raw = b"".join(b"\x00" + b"".join(bytes(p) for p in row) for row in rows)

    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


# ---------------------------------------------------------------- the project

def group_paths(project):
    """Element uuid -> folder path, from the outliner and, in a format-5 project, the groups list."""
    names = {g["uuid"]: g.get("name", "group") for g in project.get("groups", [])}
    paths = {}

    def walk(nodes, path):
        for n in nodes:
            if isinstance(n, str):
                paths[n] = path
            else:
                name = n.get("name") or names.get(n.get("uuid"), "group")
                walk(n.get("children", []), name if not path else path + "/" + name)

    walk(project.get("outliner", []), "")
    return paths


def in_group(path: str, group: str) -> bool:
    return group in path.split("/")


def centre(e):
    return [(a + b) / 2 for a, b in zip(e["from"], e["to"])]


def bounds(elements):
    """(lo, hi) over the cubes, mesh units."""
    lo = [min(min(e["from"][a], e["to"][a]) for e in elements) for a in range(3)]
    hi = [max(max(e["from"][a], e["to"][a]) for e in elements) for a in range(3)]
    return lo, hi


def moved(e, d):
    out = dict(e)
    if e.get("type", "cube") == "cube":
        out["from"] = [a - b for a, b in zip(e["from"], d)]
        out["to"] = [a - b for a, b in zip(e["to"], d)]
    if "origin" in e:
        out["origin"] = [a - b for a, b in zip(e["origin"], d)]
    return out


def subproject(project, name, elements, texture_png: bytes):
    """A project of these elements, its folders rebuilt from the paths, one texture embedded."""
    paths = group_paths(project)
    root = []
    folders = {}

    def folder(path):
        if path in folders:
            return folders[path]
        node = {"name": path.split("/")[-1], "origin": [0, 0, 0], "color": 0, "uuid": "g-" + path.replace("/", "-"),
                "export": True, "mirror_uv": False, "isOpen": False, "locked": False, "visibility": True, "autouv": 0, "children": []}
        folders[path] = node
        parent = path.rsplit("/", 1)[0] if "/" in path else None
        (folder(parent)["children"] if parent else root).append(node)
        return node

    for e in elements:
        path = paths.get(e["uuid"], "")
        (folder(path)["children"] if path else root).append(e["uuid"])
    tex = dict(project["textures"][0])
    tex["source"] = "data:image/png;base64," + base64.b64encode(texture_png).decode("ascii")
    tex["name"] = f"{name}.png"
    return {
        "meta": {"format_version": "4.10", "model_format": "free", "box_uv": False},
        "name": name, "model_identifier": "", "visible_box": [1, 1, 0], "variable_placeholders": "", "variable_placeholder_buttons": [],
        "unhandled_root_fields": {}, "resolution": project["resolution"],
        "elements": elements, "outliner": root, "textures": [tex],
    }


def untinted(project, rows, w, h, body_elements):
    """The texture with every body face's texels divided by the preview's tint."""
    out = [list(r) for r in rows]
    for e in body_elements:
        for f in e.get("faces", {}).values():
            u0, v0, u1, v1 = uv_bounds(f["uv"])
            for y in range(int(min(v0, v1)), int(max(v0, v1))):
                for x in range(int(min(u0, u1)), int(max(u0, u1))):
                    if 0 <= x < w and 0 <= y < h:
                        r, g, b, a = rows[y][x]
                        out[y][x] = (min(255, round(r * 255 / PREVIEW_TINT[0])), min(255, round(g * 255 / PREVIEW_TINT[1])),
                                     min(255, round(b * 255 / PREVIEW_TINT[2])), a)
    return out


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main(argv) -> None:
    profile_path = DATA / "vanillawheels/vehicle/trailblazer.json"
    profile_bytes = require_appearance_only(profile_path, ROOT / "devtools/art/reference/released-profile.json")
    profile = json.loads(profile_bytes)
    project = json.loads(PREVIEW.read_text(encoding="utf-8"))
    paths = group_paths(project)
    by_name = {e["name"]: e for e in project["elements"]}
    png = base64.b64decode(project["textures"][0]["source"].split(",", 1)[1])
    w, h, rows = read_png(png)

    wheel = [e for e in project["elements"] if in_group(paths.get(e["uuid"], ""), WHEEL_GROUP)]
    chest = [e for e in project["elements"] if in_group(paths.get(e["uuid"], ""), CHEST_GROUP)]
    reference = [e for e in project["elements"] if in_group(paths.get(e["uuid"], ""), "player_reference")]
    # The modelled chest stays in the preview only: the game draws its own double chest in the bed, scaled to the cube.
    body = [e for e in project["elements"] if e not in wheel and e not in chest and e not in reference and not in_group(paths.get(e["uuid"], ""), "wheels")]
    if any(f.get("texture", 0) != 0 for e in body + wheel for f in e.get("faces", {}).values()):
        raise SystemExit("a face uses a texture other than the first; only textures[0] is shipped")
    painted = [e for e in body if in_group(paths.get(e["uuid"], ""), "body")]

    # The wheel: its cubes share an origin at the axle; move them so the axle is the origin.
    axle = wheel[0]["origin"]
    wheel_r = profile["wheels"]["radius"]
    wheel_up = axle[1]
    wheel_cubes = [moved(e, axle) for e in wheel]

    body_png = write_png(w, h, untinted(project, rows, w, h, painted))
    write_json(ASSETS / "vanillawheels/mesh/trailblazer.bbmodel", subproject(project, "trailblazer", body, body_png))
    write_json(ASSETS / "vanillawheels/mesh/trailblazer_wheel.bbmodel", subproject(project, "trailblazer_wheel", wheel_cubes, png))

    assert profile_path.read_bytes() == profile_bytes
    print(f"appearance-only: {len(body)} body elements, {len(wheel_cubes)} wheel elements; gameplay profile unchanged")


if __name__ == "__main__":
    main(sys.argv)
