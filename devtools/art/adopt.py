"""Adopts the hand-built Blockbench project as the truck: splits it into what the game loads, and writes the profile.

Run from the repository root:

    uv run --no-project python devtools/art/adopt.py

Reads devtools/art/preview/trailblazer_preview.bbmodel -- the project as saved in Blockbench, the source of
the truck since Rusty's friend built its wheels and arches there -- and writes:

  src/main/resources/assets/trailblazer/vanillawheels/mesh/trailblazer.bbmodel        the body: everything but the wheels and the chest
  src/main/resources/assets/trailblazer/vanillawheels/mesh/trailblazer_wheel.bbmodel  one wheel, moved to the origin
  src/main/resources/data/trailblazer/vanillawheels/vehicle/trailblazer.json          the profile, its numbers read off the cubes
  src/main/resources/assets/trailblazer/lang/en_us.json

The preview shows the body tinted as the game paints it, so the body's texels are divided by that tint on the
way out and the game's paint multiplies back in; the chest cubes stay in the preview only, since the game draws
its own double chest there. Nothing here designs anything: change the truck in Blockbench and run this.
"""
from __future__ import annotations

import base64
import json
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODID = "trailblazer"
ASSETS = ROOT / "src/main/resources/assets" / MODID
DATA = ROOT / "src/main/resources/data" / MODID
PREVIEW = ROOT / "devtools/art/preview/trailblazer_preview.bbmodel"

# The tint the preview's body texels carry: light-blue dye lifted a quarter toward white, as Vanilla Wheels
# paints a dyed vehicle. Dividing it out gives the greys the game multiplies its paint into.
PREVIEW_TINT = (107, 198, 227)
# What an undyed truck wears in the game: the same tint, so the game shows the preview's colour.
FACTORY = "#%02x%02x%02x" % PREVIEW_TINT

WHEEL_GROUP = "wheel_0_left"
CHEST_GROUP = "trunk_chest"
SEAT_Y = 30


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


def moved(e, d):
    out = dict(e)
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
            u0, v0, u1, v1 = f["uv"]
            for y in range(int(min(v0, v1)), int(max(v0, v1))):
                for x in range(int(min(u0, u1)), int(max(u0, u1))):
                    if 0 <= x < w and 0 <= y < h:
                        r, g, b, a = out[y][x]
                        out[y][x] = (min(255, round(r * 255 / PREVIEW_TINT[0])), min(255, round(g * 255 / PREVIEW_TINT[1])),
                                     min(255, round(b * 255 / PREVIEW_TINT[2])), a)
    return out


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main(argv) -> None:
    project = json.loads(PREVIEW.read_text(encoding="utf-8"))
    paths = group_paths(project)
    by_name = {e["name"]: e for e in project["elements"]}
    png = base64.b64decode(project["textures"][0]["source"].split(",", 1)[1])
    w, h, rows = read_png(png)

    wheel = [e for e in project["elements"] if in_group(paths.get(e["uuid"], ""), WHEEL_GROUP)]
    chest = [e for e in project["elements"] if in_group(paths.get(e["uuid"], ""), CHEST_GROUP)]
    body = [e for e in project["elements"] if e not in wheel and e not in chest and not in_group(paths.get(e["uuid"], ""), "wheels")]
    painted = [e for e in body if in_group(paths.get(e["uuid"], ""), "body")]

    # The wheel: its cubes share an origin at the axle; move them so the axle is the origin.
    axle = wheel[0]["origin"]
    wheel_r = round(max(e["to"][1] - axle[1] for e in wheel), 1)
    wheel_up = axle[1]
    wheel_cubes = [moved(e, axle) for e in wheel]

    body_png = write_png(w, h, untinted(project, rows, w, h, painted))
    write_json(ASSETS / "vanillawheels/mesh/trailblazer.bbmodel", subproject(project, "trailblazer", body, body_png))
    write_json(ASSETS / "vanillawheels/mesh/trailblazer_wheel.bbmodel", subproject(project, "trailblazer_wheel", wheel_cubes, png))

    # The profile, off the cubes.
    wheels = {}
    for e in project["elements"]:
        p = paths.get(e["uuid"], "")
        for part in p.split("/"):
            if part.startswith("wheel_") and part != "wheels":
                wheels[part] = e["origin"]
    positions = sorted(wheels.values(), key=lambda o: (-o[2], o[0]))
    lens = [centre(by_name[n]) for n in ("lens_left", "lens_right")]
    lens_z = max(by_name["lens_left"]["to"][2], by_name["lens_right"]["to"][2])
    speed = centre(by_name["dial_speed"])
    fuel = centre(by_name["dial_fuel"])
    needle_z = centre(by_name["needle_speed"])[2]
    hitch = centre(by_name["hitch_ball"])
    chest_base = by_name["chest_base"]
    front_seat = centre(by_name["cushion_front_left"])
    rear_seat = centre(by_name["cushion_rear_left"])
    zs = [v for e in body for v in (e["from"][2], e["to"][2])]
    ys = [v for e in body for v in (e["from"][1], e["to"][1])]
    length = (max(zs) - min(zs)) / 16.0
    height = max(ys) / 16.0
    profile = {
        "mesh": "trailblazer:trailblazer",
        "wheel_mesh": "trailblazer:trailblazer_wheel",
        "scale": 0.0625,
        "handedness": "right",
        "body": {"width": 2.75, "length": round(length, 2), "height": round(height, 2),
                 "parts": [{"at": [0, 10, round(positions[0][2])], "width": 3.4, "height": 1.5},
                           {"at": [0, 10, round(positions[2][2])], "width": 3.4, "height": 1.5}]},
        "seats": [{"at": [8, SEAT_Y, front_seat[2]], "driver": True}, {"at": [-8, SEAT_Y, front_seat[2]]},
                  {"at": [8, SEAT_Y, rear_seat[2]]}, {"at": [-8, SEAT_Y, rear_seat[2]]}],
        "wheels": {"radius": wheel_r, "positions": [
            {"forward": positions[0][2], "right": -positions[0][0], "up": wheel_up, "steers": True},
            {"forward": positions[1][2], "right": -positions[1][0], "up": wheel_up, "steers": True},
            {"forward": positions[2][2], "right": -positions[2][0], "up": wheel_up},
            {"forward": positions[3][2], "right": -positions[3][0], "up": wheel_up}]},
        "engine": {"max_speed": 0.9, "acceleration": 0.02, "reverse_speed": 0.3, "brake": 0.05, "drag": 0.01},
        "handling": {"grip": 0.85, "steer_degrees": 32, "drift_grip": 0.12, "drift_boost": 0.3, "drift_charge_ticks": 40},
        "climb": 2.0,
        "mass": 1.45,
        "fuel": {"capacity": 24000},
        "storage": {"rows": 6, "region": {"z_max": chest_base["to"][2]},
                    "chest": {"at": [0, chest_base["from"][1], (chest_base["from"][2] + chest_base["to"][2]) / 2], "yaw": 180}},
        # The dials face the driver (-z); needles point up at rest. Seen by the driver, positive about +z is
        # clockwise, so both sweep clockwise from eight o'clock (-120 degrees) through four (+120).
        "gauges": [{"kind": "speed", "part": {"group": "needle_speed"}, "pivot": [speed[0], speed[1], needle_z], "axis": [0, 0, 1], "zero": -2.094, "sweep": 4.189},
                   {"kind": "fuel", "part": {"group": "needle_fuel"}, "pivot": [fuel[0], fuel[1], needle_z], "axis": [0, 0, 1], "zero": -2.094, "sweep": 4.189}],
        "headlights": {"at": [[lens[0][0], lens[0][1], lens_z + 0.5], [lens[1][0], lens[1][1], lens_z + 0.5]], "part": {"group": "lenses"}, "range": 10},
        "horn": "vanillawheels:horn.truck",
        "radio": {"at": [-4, 37, 12]},
        "hitch": {"rear": [0, hitch[1], hitch[2] - 2]},
        "paint": {"part": {"group": "body"}, "default": "light_blue", "factory": FACTORY},
        "glass": {"group": "windshield"},
        "sounds": {"engine": "vanillawheels:engine.petrol"},
    }
    write_json(DATA / "vanillawheels/vehicle/trailblazer.json", profile)
    write_json(ASSETS / "lang/en_us.json", {"vehicle.trailblazer.trailblazer": "Trailblazer"})
    print(f"body {len(body)} cubes ({len(painted)} painted), wheel {len(wheel_cubes)} cubes at radius {wheel_r} up {wheel_up}, "
          f"chest {len(chest)} cubes left in the preview; wheels at {[(p[2], -p[0]) for p in positions]}; length {length:.2f} height {height:.2f}")


if __name__ == "__main__":
    main(sys.argv)
