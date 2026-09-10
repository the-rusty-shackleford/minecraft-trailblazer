"""The Trailblazer's art, as code: the generated bundle normalized into what Vanilla Wheels reads.

Run from the repository root:

    uv run --no-project python devtools/art/build.py

Reads the generator's OBJ and MTL files from devtools/art/src/ (committed as
they came, see SOURCES.md there), and writes:

  src/main/resources/assets/trailblazer/vanillawheels/mesh/trailblazer.obj
  src/main/resources/assets/trailblazer/vanillawheels/mesh/trailblazer_wheel.obj
  src/main/resources/assets/trailblazer/textures/entity/trailblazer.png
  src/main/resources/data/trailblazer/vanillawheels/vehicle/trailblazer.json
  src/main/resources/assets/trailblazer/lang/en_us.json

What it changes, and why (measured on the bundle, see knowledge/decisions):

- The cab was a solid block from floor to window sill, the roof at 32 px,
  and a seated player's eye is 26 px above the seat, so the driver's head
  stood above the roof and inside the block. The cab is hollowed (a floor,
  two side walls, a bulkhead, a rear wall), the roof, pillars, glass and
  mirrors rise 8 px, the seats sit 3 px higher on the new floor, and the
  seat points put every eye 2 px under the new roof.
- The gauge cluster sat inside the hood facing the nose. It is flipped and
  moved into the cab under the windshield facing the driver, and its stub
  needles are replaced with needles as long as the dials' radius, pivoted
  at the dial centres.
- The steering wheel rises to sit under the dials and comes toward the
  driver, its column shortened to the bulkhead; the gear stick stands on
  the new floor.
- The atlas is regenerated as an 8 x 8 grid of 32 px swatches so the
  seventeenth material (the needles) has a cell, the body swatches are
  greys so the dye colour multiplies in, and the glass has alpha.
- Every face's UVs are rewritten onto its material's new cell, keeping the
  face's own orientation within the cell.

The bundle is left-handed (+X is the vehicle's right with +Z forward), so
the profile says so and Vanilla Wheels mirrors it once at load. Everything
here stays in the bundle's frame, in pixels.
"""
from __future__ import annotations

import json
import math
import struct
import sys
import zlib
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = Path(__file__).resolve().parent / "src"
MODID = "trailblazer"
ASSETS = ROOT / "src/main/resources/assets" / MODID
DATA = ROOT / "src/main/resources/data" / MODID


# ---------------------------------------------------------------- PNG writing

def write_png(path: Path, width: int, height: int, pixels) -> None:
    raw = b"".join(b"\x00" + b"".join(bytes(p) for p in row) for row in pixels)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


class Noise:
    def __init__(self, seed: int) -> None:
        self.state = seed & 0xFFFFFFFF

    def next(self) -> float:
        self.state = (1664525 * self.state + 1013904223) & 0xFFFFFFFF
        return self.state / 0xFFFFFFFF


# ---------------------------------------------------------------- the mesh

class Face:
    __slots__ = ("material", "corners", "uv")

    def __init__(self, material, corners, uv):
        self.material = material
        self.corners = corners      # list of (x, y, z)
        self.uv = uv                # list of (fu, fv) in 0..1 within the material's cell


def read_mtl(path: Path):
    """Material name -> Kd colour (0..255 ints)."""
    colours = {}
    name = None
    for line in path.read_text().splitlines():
        t = line.split()
        if not t:
            continue
        if t[0] == "newmtl":
            name = t[1]
        elif t[0] == "Kd" and name:
            colours[name] = tuple(int(round(float(c) * 255)) for c in t[1:4])
    return colours


def read_obj(path: Path):
    """The faces of an OBJ, with their UVs reduced to fractions of whatever 4 x 4 cell they sat in."""
    v, vt, faces, material = [], [], [], None
    for line in path.read_text().splitlines():
        t = line.split()
        if not t:
            continue
        if t[0] == "v":
            v.append(tuple(float(c) for c in t[1:4]))
        elif t[0] == "vt":
            vt.append((float(t[1]), float(t[2])))
        elif t[0] == "usemtl":
            material = t[1]
        elif t[0] == "f":
            corners, uvs = [], []
            for c in t[1:]:
                parts = c.split("/")
                corners.append(v[int(parts[0]) - 1])
                uvs.append(vt[int(parts[1]) - 1] if len(parts) > 1 and parts[1] else (0.0, 0.0))
            u0 = math.floor(min(u for u, _ in uvs) * 4 + 1e-6)
            v0 = math.floor(min(w for _, w in uvs) * 4 + 1e-6)
            frac = [(min(1.0, max(0.0, u * 4 - u0)), min(1.0, max(0.0, w * 4 - v0))) for u, w in uvs]
            faces.append(Face(material, corners, inset(frac)))
    return faces


# Every UV is kept this far inside its swatch: a coordinate on the swatch's
# edge samples the neighbour, or the atlas's empty padding, whose alpha is
# zero -- and the cutout shader then drops the whole face. The bundle's
# polygon caps carry one coordinate for every corner, right on the corner.
INSET = 0.06


def inset(uvs):
    return [(INSET + (1 - 2 * INSET) * u, INSET + (1 - 2 * INSET) * v) for u, v in uvs]


def pieces(faces):
    """Faces grouped into connected pieces (shared vertex coordinates), each with its bounds."""
    parent = {}

    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for f in faces:
        keys = [tuple(round(c, 4) for c in p) for p in f.corners]
        for k in keys[1:]:
            union(keys[0], k)
    groups = defaultdict(list)
    for f in faces:
        groups[find(tuple(round(c, 4) for c in f.corners[0]))].append(f)
    out = []
    for fs in groups.values():
        pts = [p for f in fs for p in f.corners]
        lo = tuple(min(p[k] for p in pts) for k in range(3))
        hi = tuple(max(p[k] for p in pts) for k in range(3))
        out.append(Piece(fs, lo, hi))
    return out


class Piece:
    def __init__(self, faces, lo, hi):
        self.faces = faces
        self.lo = lo
        self.hi = hi
        self.materials = sorted({f.material for f in faces})

    def within(self, x=None, y=None, z=None, material=None):
        """Whether the piece's bounds sit inside the given ranges (each (lo, hi) or None) and it uses the material."""
        for rng, lo, hi in ((x, self.lo[0], self.hi[0]), (y, self.lo[1], self.hi[1]), (z, self.lo[2], self.hi[2])):
            if rng is not None and not (rng[0] - 1e-6 <= lo and hi <= rng[1] + 1e-6):
                return False
        return material is None or material in self.materials

    def map(self, fn):
        for f in self.faces:
            f.corners = [fn(p) for p in f.corners]


def box(material, x0, y0, z0, x1, y1, z1):
    """Six quads wound outward, each on the whole of the material's cell."""
    c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    uv = inset([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (1, 2, 6, 5), (0, 4, 7, 3)]
    return [Face(material, [c[i] for i in q], list(uv)) for q in quads]


def stretch(piece, axis, lo=None, hi=None):
    """Moves the piece's faces at its low or high bound on an axis to a new value: a box gets taller, not moved."""
    old_lo, old_hi = piece.lo[axis], piece.hi[axis]

    def fn(p):
        p = list(p)
        if lo is not None and abs(p[axis] - old_lo) < 1e-6:
            p[axis] = lo
        if hi is not None and abs(p[axis] - old_hi) < 1e-6:
            p[axis] = hi
        return tuple(p)

    piece.map(fn)


def shift(piece, dx=0.0, dy=0.0, dz=0.0):
    piece.map(lambda p: (p[0] + dx, p[1] + dy, p[2] + dz))


# ---------------------------------------------------------------- the cab repair

ROOF_RISE = 8.0
SEAT_RISE = 3.0
# The cluster: flipped in z about 17.3 and pushed to sit on the bulkhead's inner face, raised to the dash.
CLUSTER_FLIP = 2 * 17.3 + 0.95
CLUSTER_RISE = 11.0
NEEDLE_LENGTH = 2.1
DIAL_LIFT = 0.4
WHEEL_RISE = 4.0
WHEEL_TOWARD = 3.4
SPEED_PIVOT = (-8.0, 17.0 + CLUSTER_RISE, CLUSTER_FLIP - 21.9)
FUEL_PIVOT = (-2.0, 17.0 + CLUSTER_RISE, CLUSTER_FLIP - 21.9)


def repair(faces):
    """The cab repair on the truck's pieces; returns the new face list."""
    ps = pieces(faces)
    keep = []
    added = []
    for p in ps:
        # The solid cab: replaced by a floor, two side walls, a bulkhead under the windshield, and a rear wall.
        if p.within(x=(-15, 15), y=(10, 25), z=(-15, 17), material="body_blue") and len(p.faces) == 6:
            added += box("body_blue", -15, 10, -15, 15, 12, 17)
            added += box("body_blue", -15, 12, -15, -13, 25, 17)
            added += box("body_blue", 13, 12, -15, 15, 25, 17)
            added += box("body_blue", -15, 12, 15, 15, 25, 17)
            added += box("body_blue", -15, 12, -15, 15, 25, -13)
            continue
        # The roof rises; the pillars, the rear shell, the B-pillar strips and the glass reach up to it.
        if p.within(x=(-16, 16), y=(28, 32), z=(-17, 18), material="body_blue"):
            shift(p, dy=ROOF_RISE)
        elif p.within(y=(18, 31), z=(-17, 18), material="metal") and abs(p.hi[0] - p.lo[0]) <= 2.01 and p.hi[1] - p.lo[1] > 10:
            stretch(p, 1, hi=28 + ROOF_RISE)
        elif p.within(x=(-15, 15), y=(12, 28), z=(-19, -14), material="body_blue_dark"):
            stretch(p, 1, hi=28 + ROOF_RISE)
        elif p.within(y=(12, 25), material="body_blue_shadow") and p.hi[2] - p.lo[2] <= 1.01:
            stretch(p, 1, hi=28 + ROOF_RISE)
        elif p.within(y=(22, 28), material="glass") and p.hi[0] - p.lo[0] <= 1.0:
            stretch(p, 1, lo=25, hi=28 + ROOF_RISE)
        elif p.within(x=(-12, 12), y=(19.5, 27.5), z=(16.5, 17.2), material="glass"):
            stretch(p, 1, lo=25, hi=28 + ROOF_RISE)
        elif p.within(x=(-13, 13), y=(18.5, 28.5), z=(17, 17.5), material="metal"):
            stretch(p, 1, lo=24.5, hi=29 + ROOF_RISE)
        elif p.within(y=(22, 31), z=(6, 12)) and p.lo[0] >= 17 or p.within(y=(22, 31), z=(6, 12)) and p.hi[0] <= -17:
            shift(p, dy=ROOF_RISE)
        # The seats sit on the new floor.
        elif p.within(y=(9, 24), z=(-11, 12), material="black") and p.hi[0] - p.lo[0] == 10:
            shift(p, dy=SEAT_RISE)
        # The gear stick on the centreline stands on the new floor.
        elif p.within(x=(-1, 1), y=(11, 18), z=(8, 11), material="metal") or p.within(x=(-2, 2), y=(10, 12), z=(8, 11), material="black"):
            shift(p, dy=SEAT_RISE)
        # The steering wheel -- a ring of small blocks about (-9, 17) on the bulkhead -- rises to sit
        # under the dials and comes toward the driver; its column shortens to reach the bulkhead.
        elif p.within(x=(-14, -4), y=(12, 22), z=(14.5, 15.5), material="black") and len(p.faces) == 6:
            shift(p, dy=WHEEL_RISE, dz=-WHEEL_TOWARD)
        elif p.within(x=(-10.3, -7.7), y=(14.5, 17.5), z=(9, 15), material="metal") and len(p.faces) == 14:
            # The column: its far end stays on the bulkhead, its near end comes to the ring.
            p.map(lambda q: (q[0], q[1] + WHEEL_RISE, 15 - (15 - q[2]) * (1 - WHEEL_TOWARD / 6.0)))
        elif p.within(x=(-10.3, -7.7), y=(16, 18), z=(14.5, 16), material="metal"):
            shift(p, dy=WHEEL_RISE, dz=-WHEEL_TOWARD)
        # The cluster: bezels, dials and ticks flip to face the driver and rise to the dash; the stub needles go.
        elif p.within(z=(20.5, 22.2)) and set(p.materials) <= {"black", "gauge_dark", "gauge", "needle"}:
            if p.materials == ["needle"]:
                continue
            # Dials and ticks come a little further off the bezels than they sat, so the faces do not fight.
            toward = 0.0 if p.materials == ["black"] else DIAL_LIFT
            p.map(lambda q: (q[0], q[1] + CLUSTER_RISE, CLUSTER_FLIP - q[2] - toward))
        keep.append(p)
    out = [f for p in keep for f in p.faces] + added
    # New needles: a thin bar from each pivot up to the dial's rim, ahead of the ticks.
    for px, py, pz in (SPEED_PIVOT, FUEL_PIVOT):
        out += box("needle", px - 0.18, py - 0.2, pz - DIAL_LIFT - 0.9, px + 0.18, py + NEEDLE_LENGTH, pz - DIAL_LIFT - 0.6)
    return out


# ---------------------------------------------------------------- the atlas

CELL = 32
GRID = 8
# Paint materials are greys in the ratio of the bundle's blues, so a dye reproduces the shading.
PAINT_GREY = {"body_blue": 240, "body_blue_hi": 255, "body_blue_dark": 171, "body_blue_shadow": 129}
GLASS_ALPHA = 150


def cells(materials):
    return {m: (i % GRID, i // GRID) for i, m in enumerate(sorted(materials))}


def atlas(materials, colours):
    noise = Noise(0x7B1A)
    px = [[(0, 0, 0, 0) for _ in range(CELL * GRID)] for _ in range(CELL * GRID)]
    for m, (cx, cy) in cells(materials).items():
        if m in PAINT_GREY:
            base = (PAINT_GREY[m],) * 3
        else:
            base = colours.get(m, (200, 0, 200))
        alpha = GLASS_ALPHA if m.startswith("glass") else 255
        for y in range(CELL):
            for x in range(CELL):
                d = int((noise.next() - 0.5) * 14)
                c = tuple(max(0, min(255, v + d)) for v in base)
                px[cy * CELL + y][cx * CELL + x] = (*c, alpha)
    return px


# ---------------------------------------------------------------- writing

def write_obj(path: Path, faces, cell_of, note: str):
    lines = [f"# {note}", "# generated by devtools/art/build.py; the source bundle is under devtools/art/src"]
    v_index = {}
    vs = []
    vts = []
    vt_index = {}
    by_material = defaultdict(list)
    for f in faces:
        by_material[f.material].append(f)
    for m in sorted(by_material):
        cx, cy = cell_of[m]
        for f in by_material[m]:
            for (x, y, z), (fu, fv) in zip(f.corners, f.uv):
                k = (round(x, 4), round(y, 4), round(z, 4))
                if k not in v_index:
                    v_index[k] = len(vs) + 1
                    vs.append(k)
                u = (cx + fu) / GRID
                w = 1.0 - (cy + 1 - fv) / GRID
                t = (round(u, 5), round(w, 5))
                if t not in vt_index:
                    vt_index[t] = len(vts) + 1
                    vts.append(t)
    for x, y, z in vs:
        lines.append(f"v {x:.4f} {y:.4f} {z:.4f}")
    for u, w in vts:
        lines.append(f"vt {u:.5f} {w:.5f}")
    for m in sorted(by_material):
        cx, cy = cell_of[m]
        lines.append(f"usemtl {m}")
        for f in by_material[m]:
            ref = []
            for (x, y, z), (fu, fv) in zip(f.corners, f.uv):
                vi = v_index[(round(x, 4), round(y, 4), round(z, 4))]
                u = (cx + fu) / GRID
                w = 1.0 - (cy + 1 - fv) / GRID
                ti = vt_index[(round(u, 5), round(w, 5))]
                ref.append(f"{vi}/{ti}")
            lines.append("f " + " ".join(ref))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- the profile

def profile():
    roof = 32 + ROOF_RISE
    seat_y = roof - 2 - 26
    return {
        "mesh": "trailblazer:trailblazer",
        "wheel_mesh": "trailblazer:trailblazer_wheel",
        "texture": "trailblazer:textures/entity/trailblazer.png",
        "scale": 0.0625,
        "handedness": "left",
        "body": {"width": 2.75, "length": 5.45, "height": roof / 16,
                 "parts": [{"at": [0, 3, 22], "width": 2.75, "height": 1.35}, {"at": [0, 3, -26], "width": 2.6, "height": 1.4},
                           {"at": [0, 3, 40], "width": 2.4, "height": 1.0}]},
        "seats": [{"at": [-8, seat_y, 6], "driver": True}, {"at": [8, seat_y, 6]}, {"at": [-8, seat_y, -8]}, {"at": [8, seat_y, -8]}],
        "wheels": {"radius": 12, "positions": [{"forward": 23.5, "right": -18, "steers": True}, {"forward": 23.5, "right": 18, "steers": True},
                                              {"forward": -22.5, "right": -18}, {"forward": -22.5, "right": 18}]},
        "engine": {"max_speed": 0.9, "acceleration": 0.02, "reverse_speed": 0.3, "brake": 0.05, "drag": 0.01},
        "handling": {"grip": 0.85, "steer_degrees": 32, "drift_grip": 0.4, "drift_boost": 0.3, "drift_charge_ticks": 40},
        "climb": 2.0,
        "mass": 1.45,
        "fuel": {"capacity": 24000},
        "storage": {"rows": 6, "region": {"y_min": 14, "z_min": -31, "z_max": -12}},
        # Needles point up at rest. Seen by the driver, the speedometer sweeps clockwise from eight o'clock
        # to four; the fuel gauge from eight (empty) to four (full). The bundle is mirrored at load, which
        # negates every angle, so these are the driver's angles with their signs flipped.
        "gauges": [{"kind": "speed", "part": {"material": "needle", "x_max": -5}, "pivot": list(SPEED_PIVOT), "axis": [0, 0, 1], "zero": 2.094, "sweep": -4.189},
                   {"kind": "fuel", "part": {"material": "needle", "x_min": -5}, "pivot": list(FUEL_PIVOT), "axis": [0, 0, 1], "zero": 2.094, "sweep": -4.189}],
        "headlights": {"at": [[-13, 15.5, 40.5], [13, 15.5, 40.5]], "part": {"material": "gauge", "z_min": 36}, "range": 10},
        "horn": "vanillawheels:horn.truck",
        "radio": {"at": [3, 26, 14]},
        "hitch": {"rear": [0, 7.5, -42]},
        "paint": {"part": {"material": ["body_blue", "body_blue_hi", "body_blue_dark", "body_blue_shadow"]}, "default": "light_blue"},
        "glass": {"material": ["glass", "glass_hi"]},
        "sounds": {"engine": "vanillawheels:engine.petrol"},
    }


def main(argv) -> None:
    colours = read_mtl(SRC / "trailblazer_frame.mtl")
    frame = repair(read_obj(SRC / "trailblazer_frame.obj"))
    wheel = read_obj(SRC / "trailblazer_wheel.obj")
    materials = sorted(set(colours) | {f.material for f in frame} | {f.material for f in wheel})
    cell_of = cells(materials)
    write_obj(ASSETS / "vanillawheels/mesh/trailblazer.obj", frame, cell_of, "The Trailblazer, pixels, +Z forward, left-handed")
    write_obj(ASSETS / "vanillawheels/mesh/trailblazer_wheel.obj", wheel, cell_of, "The Trailblazer's wheel, pixels, axle along X")
    write_png(ASSETS / "textures/entity/trailblazer.png", CELL * GRID, CELL * GRID, atlas(materials, colours))
    write_json(DATA / "vanillawheels/vehicle/trailblazer.json", profile())
    write_json(ASSETS / "lang/en_us.json", {"vehicle.trailblazer.trailblazer": "Trailblazer"})
    print(f"wrote the truck ({len(frame)} faces), the wheel ({len(wheel)} faces), the atlas ({len(materials)} cells), the profile")
    print("seat points at y", profile()["seats"][0]["at"][1], "; dial pivots", SPEED_PIVOT, FUEL_PIVOT)


if __name__ == "__main__":
    main(sys.argv)
