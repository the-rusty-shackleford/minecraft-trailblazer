"""The Trailblazer's art, as code: a Blockbench project for the truck and one for its wheel, and the profile.

Run from the repository root:

    uv run --no-project python devtools/art/build.py

Writes:

  src/main/resources/assets/trailblazer/vanillawheels/mesh/trailblazer.bbmodel
  src/main/resources/assets/trailblazer/vanillawheels/mesh/trailblazer_wheel.bbmodel
  src/main/resources/data/trailblazer/vanillawheels/vehicle/trailblazer.json
  src/main/resources/assets/trailblazer/lang/en_us.json

The truck is a box model designed here, to the reference Rusty gave: an
open-top, roll-caged, light-blue pickup with a slotted grille, angular
black fenders over big treaded tyres, a raked windshield in a grey frame,
grey bumpers with hooks and a winch, black seats, side mirrors. It is
written as a Blockbench project (cubes, each with a rotation about an
origin and a texture rectangle per face; folders in the outliner; the
texture embedded) so that Blockbench opens it as it is and every part can
be moved or repainted there, and Vanilla Wheels reads the saved file
back. The frame is Blockbench's, which is Minecraft's: +Z forward (the
"south" side is the nose), +Y up, +X the vehicle's left; units are
pixels, sixteen to a block.

Every face gets its own patch of the texture at one texel per pixel (more
on the dials and the lenses), painted here: a three-tone pixel noise per
material, and drawn detail where a face is something -- the grille's
seven slots, the lenses, the bonnet vents, the door seams, the tail
lights, and the tread, the rims and the dials, which are painted by where
each texel is in the world so a turned slab of a tyre gets its share of
the pattern. Body faces are greys so the dye colour multiplies in.

Selectors in the profile name folders and elements, never materials: a
project with one texture has one material.
"""
from __future__ import annotations

import base64
import json
import math
import struct
import sys
import uuid as uuidlib
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODID = "trailblazer"
ASSETS = ROOT / "src/main/resources/assets" / MODID
DATA = ROOT / "src/main/resources/data" / MODID


# ---------------------------------------------------------------- PNG writing

def png_bytes(width: int, height: int, pixels) -> bytes:
    raw = b"".join(b"\x00" + b"".join(bytes(p) for p in row) for row in pixels)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


class Noise:
    def __init__(self, seed: int) -> None:
        self.state = (seed * 2654435761 + 1) & 0xFFFFFFFF

    def next(self) -> float:
        self.state = (1664525 * self.state + 1013904223) & 0xFFFFFFFF
        return self.state / 0xFFFFFFFF


# ---------------------------------------------------------------- materials

# Three tones each: base, light, dark. The body's are greys: the dye multiplies in.
TONES = {
    "body": ((236, 236, 236), (250, 250, 250), (214, 214, 214)),
    "rubber": ((38, 40, 46), (56, 58, 64), (26, 28, 32)),
    "tyre": ((40, 42, 46), (92, 94, 100), (26, 28, 30)),
    "metal": ((166, 170, 178), (196, 200, 208), (130, 134, 142)),
    "metal_dark": ((92, 96, 104), (110, 114, 122), (72, 76, 84)),
    "seat": ((30, 30, 34), (44, 44, 48), (20, 20, 22)),
    "seat_light": ((74, 76, 82), (90, 92, 98), (60, 62, 66)),
    "floor": ((58, 60, 66), (70, 72, 78), (46, 48, 52)),
    "dash": ((48, 50, 56), (62, 64, 70), (36, 38, 42)),
    "lamp": ((238, 232, 196), (255, 252, 230), (214, 206, 160)),
    "glass": ((196, 228, 242), (232, 246, 252), (172, 214, 234)),
    "needle": ((214, 48, 40), (236, 70, 60), (180, 34, 30)),
    "tail": ((196, 36, 30), (224, 60, 50), (160, 26, 22)),
    "hub": ((150, 152, 158), (174, 176, 182), (124, 126, 132)),
}
ALPHA = {"glass": 90}
GLASS_PANE, GLASS_EDGE, GLASS_STREAK = 50, 110, 150
DETAIL = {"dial": 4, "lens": 2, "rim": 2, "hubcap": 2}


# ---------------------------------------------------------------- geometry

def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def scale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def length(a):
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def rotate(p, origin, r):
    """Blockbench's turn: about the origin, X then Y then Z, degrees."""
    x, y, z = sub(p, origin)
    a, b, g = (math.radians(v) for v in r)
    y, z = y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a)
    x, z = x * math.cos(b) + z * math.sin(b), -x * math.sin(b) + z * math.cos(b)
    x, y = x * math.cos(g) - y * math.sin(g), x * math.sin(g) + y * math.cos(g)
    return add((x, y, z), origin)


class FaceRef:
    """One face of a cube: its material, its decal, its world corners in texture order, and the atlas rect it gets."""
    __slots__ = ("cube", "direction", "material", "decal", "corners", "rect")

    def __init__(self, cube, direction, material, decal, corners):
        self.cube = cube
        self.direction = direction
        self.material = material
        self.decal = decal
        self.corners = corners
        self.rect = None


class Cube:
    __slots__ = ("name", "folder", "lo", "hi", "origin", "rotation", "material", "faces", "decals", "uuid", "refs")

    def __init__(self, name, folder, lo, hi, material, rotation=(0, 0, 0), origin=None, faces=None, decals=None):
        self.name = name
        self.folder = folder
        self.lo = lo
        self.hi = hi
        self.material = material
        self.rotation = rotation
        self.origin = origin if origin is not None else ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2)
        self.faces = faces or {}
        self.decals = decals or {}
        self.uuid = str(uuidlib.uuid5(uuidlib.NAMESPACE_URL, f"{folder}/{name}/{lo}/{hi}/{rotation}"))
        self.refs = []

    def corners(self, direction):
        """The face's corners, top-left, top-right, bottom-right, bottom-left as seen from outside, after the turn."""
        x0, y0, z0 = self.lo
        x1, y1, z1 = self.hi
        c = {
            "north": [(x1, y1, z0), (x0, y1, z0), (x0, y0, z0), (x1, y0, z0)],
            "south": [(x0, y1, z1), (x1, y1, z1), (x1, y0, z1), (x0, y0, z1)],
            "east": [(x1, y1, z1), (x1, y1, z0), (x1, y0, z0), (x1, y0, z1)],
            "west": [(x0, y1, z0), (x0, y1, z1), (x0, y0, z1), (x0, y0, z0)],
            "up": [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],
            "down": [(x0, y0, z1), (x1, y0, z1), (x1, y0, z0), (x0, y0, z0)],
        }[direction]
        return [rotate(p, self.origin, self.rotation) for p in c]


DIRECTIONS = ("north", "south", "east", "west", "up", "down")
# The model's own words for a cube's sides: the nose is +Z, Blockbench's south.
SIDE = {"front": "south", "back": "north", "left": "east", "right": "west", "top": "up", "bottom": "down"}

CUBES = []


def cube(name, folder, x0, y0, z0, x1, y1, z1, material, rotation=(0, 0, 0), origin=None, faces=None, decals=None):
    c = Cube(name, folder, (min(x0, x1), min(y0, y1), min(z0, z1)), (max(x0, x1), max(y0, y1), max(z0, z1)), material, rotation, origin,
             {SIDE[k]: v for k, v in (faces or {}).items()}, {SIDE[k]: v for k, v in (decals or {}).items()})
    CUBES.append(c)
    return c


# ---------------------------------------------------------------- the truck

WHEEL_R = 15.0
WHEEL_W = 12.0
FRONT_AXLE = 33
REAR_AXLE = -37
TRACK = 24
# The body's datum lines, measured off the reference against its tyre: the bonnet and the tub's top edge at
# 1.27 tyres over the ground, the fenders' tops three pixels under that, the cage's top at 1.87 tyres.
TUB_TOP = 38
FENDER_TOP = 35
CAGE_TOP = 56
NOSE = 46
TAIL = -52


def truck():
    CUBES.clear()
    B = "body"
    # --- the tub: floor, sides, tailgate; the doors as proud panels with a seam painted round them; a marker
    # lamp on each front corner
    cube("floor", "tub", -18, 12, TAIL + 2, 18, 16, 16, "floor")
    cube("side_left", "body/tub", 18, 16, TAIL, 21, TUB_TOP, 16, B, decals={"left": "flank"})
    cube("side_right", "body/tub", -21, 16, TAIL, -18, TUB_TOP, 16, B, decals={"right": "flank"})
    cube("tailgate", "body/tub", -21, 16, TAIL, 21, TUB_TOP, TAIL + 2, B, decals={"back": "tailgate"})
    cube("tail_sill", "body/tub", -21, 12, TAIL, 21, 16, TAIL + 2, B)
    for sx, side in ((1, "left"), (-1, "right")):
        x0, x1 = (21, 22) if sx > 0 else (-22, -21)
        cube(f"door_front_{side}", "body/doors", x0, 17, -4, x1, TUB_TOP - 1, 11, B, decals={side: "door"})
        cube(f"door_rear_{side}", "body/doors", x0, 17, -21, x1, TUB_TOP - 1, -5, B, decals={side: "door"})
        hx0, hx1 = (22, 23) if sx > 0 else (-23, -22)
        cube(f"handle_front_{side}", "handles", hx0, 30, 6, hx1, 31, 10, "metal")
        cube(f"handle_rear_{side}", "handles", hx0, 30, -11, hx1, 31, -7, "metal")
        mx0, mx1 = (19, 21.5) if sx > 0 else (-21.5, -19)
        cube(f"marker_{side}", "lights", mx0, 26, NOSE - 3, mx1, 28, NOSE - 1, "metal")
    # --- the bonnet over the engine bay, the vents at its cowl; the nose is a slab whose face is the grille,
    # the lamps proud of it at its top corners
    cube("bonnet", "body/bonnet", -20, 30, 12, 20, TUB_TOP, NOSE - 2, B, decals={"top": "bonnet"})
    cube("engine_bay", "body/bonnet", -20, 21, 16, 20, 30, NOSE - 2, B)
    cube("nose", "body/bonnet", -20, 21, NOSE - 2, 20, TUB_TOP, NOSE, B, decals={"front": "grille"})
    for sx, side in ((1, "left"), (-1, "right")):
        x0, x1 = (12, 18) if sx > 0 else (-18, -12)
        cube(f"lens_{side}", "lamps/lenses", x0, 29, NOSE, x1, 36, NOSE + 1, "lamp", decals={"front": "lamp"})
    # --- fenders: black, a thick flat top three pixels under the bonnet line, a wedge angled down to the bumper
    # ahead of the front wheel and behind the rear one, a solid block under the front wedge beside the grille,
    # a straight leg down to the rocker behind the front wheel and ahead of the rear one (a door sits right
    # behind each arch, so there is no room for the reference's angled one); the rocker step between them
    for sx, side in ((1, "left"), (-1, "right")):
        x0, x1 = (20, 29) if sx > 0 else (-29, -20)
        fx = (x0 + x1) / 2
        cube(f"fender_front_{side}", "fenders", x0, FENDER_TOP - 4, 12, x1, FENDER_TOP, NOSE, "rubber")
        cube(f"fender_nose_{side}", "fenders", x0, FENDER_TOP - 4, NOSE, x1, FENDER_TOP, NOSE + 12, "rubber", rotation=(45, 0, 0), origin=(fx, FENDER_TOP, NOSE))
        cube(f"fender_front_block_{side}", "fenders", x0, 22, NOSE - 2, x1, FENDER_TOP - 4, NOSE + 1, "rubber")
        lx0, lx1 = (x1 - 3, x1) if sx > 0 else (x0, x0 + 3)
        cube(f"fender_leg_front_{side}", "fenders", lx0, 15, 12, lx1, FENDER_TOP - 4, 15, "rubber")
        cube(f"fender_rear_{side}", "fenders", x0, FENDER_TOP - 4, TAIL, x1, FENDER_TOP, -21, "rubber")
        cube(f"fender_tail_{side}", "fenders", x0, FENDER_TOP - 4, TAIL - 9, x1, FENDER_TOP, TAIL, "rubber", rotation=(-45, 0, 0), origin=(fx, FENDER_TOP, TAIL))
        cube(f"fender_leg_rear_{side}", "fenders", lx0, 15, -24, lx1, FENDER_TOP - 4, -21, "rubber")
        sx0, sx1 = (21, 28) if sx > 0 else (-28, -21)
        cube(f"step_{side}", "fenders", sx0, 12, -24, sx1, 15, 15, "metal_dark")
    # --- bumpers with chamfered ends; hook lamps and a winch on the front one, the hitch ball on the rear
    BUMPER = (13, 21)
    cube("bumper_front", "bumpers", -28, BUMPER[0], NOSE, 28, BUMPER[1], NOSE + 8, "metal", decals={"front": "bumper"})
    cube("bumper_rear", "bumpers", -28, BUMPER[0], TAIL - 6, 28, BUMPER[1], TAIL, "metal", decals={"back": "bumper"})
    for sx, side in ((1, "left"), (-1, "right")):
        x0, x1 = (28, 35) if sx > 0 else (-35, -28)
        cube(f"bumper_end_front_{side}", "bumpers", x0, BUMPER[0], NOSE, x1, BUMPER[1], NOSE + 8, "metal", rotation=(0, 32 * sx, 0), origin=(28 * sx, 17, NOSE + 4), decals={"front": "bumper"})
        cube(f"bumper_end_rear_{side}", "bumpers", x0, BUMPER[0], TAIL - 6, x1, BUMPER[1], TAIL, "metal", rotation=(0, -32 * sx, 0), origin=(28 * sx, 17, TAIL - 3), decals={"back": "bumper"})
        fx0, fx1 = (20, 25) if sx > 0 else (-25, -20)
        cube(f"hook_lamp_{side}", "bumpers", fx0, BUMPER[1], NOSE + 3, fx1, BUMPER[1] + 5, NOSE + 7, "metal", decals={"front": "hook"})
    cube("winch", "bumpers", -7, BUMPER[1], NOSE + 1, 7, BUMPER[1] + 6, NOSE + 6, "metal_dark")
    cube("winch_drum", "bumpers", -4, BUMPER[1] + 1, NOSE + 6, 4, BUMPER[1] + 5, NOSE + 8, "metal", decals={"front": "drum"})
    cube("winch_cable", "bumpers", -0.5, BUMPER[0] + 4, NOSE + 8, 0.5, BUMPER[1] + 1, NOSE + 9, "metal_dark")
    cube("winch_hook", "bumpers", -1.5, BUMPER[0] + 1, NOSE + 7.5, 1.5, BUMPER[0] + 4, NOSE + 9.5, "metal_dark")
    cube("hitch_post", "bumpers", -1, BUMPER[0] + 1, TAIL - 7, 1, BUMPER[1], TAIL - 4, "metal_dark")
    cube("hitch_ball", "bumpers", -2, BUMPER[1], TAIL - 8, 2, BUMPER[1] + 2, TAIL - 4, "metal")
    for sx, side in ((1, "left"), (-1, "right")):
        x0, x1 = (13, 19) if sx > 0 else (-19, -13)
        cube(f"tail_light_{side}", "lights", x0, 27, TAIL - 1, x1, 33, TAIL, "tail", decals={"back": "tail"})
    cube("exhaust", "bumpers", 9, 11, TAIL - 5, 11, 13, TAIL + 8, "metal_dark")
    # --- the windshield: one raked frame -- base rail, two pillars -- turned together about the base's
    # centreline, the glass inset in it, all running up into a level header that is one bar with the cage.
    # A turn about +X by a positive angle carries the top toward +Z, the nose: a windshield leans back, so its
    # rake is negative. The base rail starts down inside the bonnet and dash so that, turned, no edge of it
    # lifts clear of them.
    T = 4
    RAKE = -14
    PIVOT = (0, 40, 14)
    cube("windshield_base", "cage/windshield_frame", -21, 36, 12, 21, 41, 16, "metal", rotation=(RAKE, 0, 0), origin=PIVOT)
    for sx, side in ((1, "left"), (-1, "right")):
        x0, x1 = (17, 17 + T) if sx > 0 else (-17 - T, -17)
        cube(f"a_pillar_{side}", "cage/windshield_frame", x0, 41, 12, x1, CAGE_TOP - 1, 16, "metal", rotation=(RAKE, 0, 0), origin=PIVOT)
    cube("windshield", "windshield", -17, 41, 13.75, 17, CAGE_TOP - T + 1, 14.25, "glass", rotation=(RAKE, 0, 0), origin=PIVOT, decals={"front": "glass", "back": "glass"})
    pillar_rear = rotate((0, CAGE_TOP - T, 12), PIVOT, (RAKE, 0, 0))[2]
    pillar_front = rotate((0, CAGE_TOP - 1, 16), PIVOT, (RAKE, 0, 0))[2]
    header_back = math.floor(pillar_rear - 0.5)
    header_front = round(pillar_front, 2)
    cube("header", "cage/windshield_frame", -21, CAGE_TOP - T, header_back, 21, CAGE_TOP, header_front, "metal")
    # --- the cage: a flat rectangle over the front seats, a post at the doors' seam and a hoop behind the
    # front row, a brace from each rear corner down and back to the tub over the rear wheel
    HOOP = -20
    for sx, side in ((1, "left"), (-1, "right")):
        x0, x1 = (17, 17 + T) if sx > 0 else (-17 - T, -17)
        cube(f"roof_rail_{side}", "cage", x0, CAGE_TOP - T, HOOP - T, x1, CAGE_TOP, header_back + 0.5, "metal")
        cube(f"b_post_{side}", "cage", x0, TUB_TOP, -8, x1, CAGE_TOP - T, -4, "metal")
        cube(f"hoop_post_{side}", "cage", x0, TUB_TOP, HOOP - T, x1, CAGE_TOP - T, HOOP, "metal")
        cube(f"brace_{side}", "cage", x0, CAGE_TOP - T, HOOP - T - 24, x1, CAGE_TOP, HOOP - T, "metal", rotation=(-40, 0, 0), origin=((x0 + x1) / 2, CAGE_TOP - T / 2, HOOP - T))
    cube("hoop_bar", "cage", -21, CAGE_TOP - T, HOOP - T, 21, CAGE_TOP, HOOP, "metal")
    cube("cross_bar", "cage", -21, CAGE_TOP - T, -8, 21, CAGE_TOP, -4, "metal")
    # --- mirrors on the pillars
    for sx, side in ((1, "left"), (-1, "right")):
        ax0, ax1 = (21, 27) if sx > 0 else (-27, -21)
        mx0, mx1 = (23, 29) if sx > 0 else (-29, -23)
        cube(f"mirror_arm_{side}", "mirrors", ax0, 46, 12, ax1, 47, 13, "metal_dark")
        cube(f"mirror_{side}", "mirrors", mx0, 42, 11.5, mx1, 51, 13.5, "metal", decals={"back": "mirror"})
    # --- inside: seats, dash, binnacle with the dials, steering wheel, gear stick
    for row, (sz0, sz1) in (("front", (-5, 7)), ("rear", (-24, -12))):
        for sx, side in ((1, "left"), (-1, "right")):
            x0, x1 = (3, 14) if sx > 0 else (-14, -3)
            cube(f"cushion_{row}_{side}", "seats", x0, 17, sz0, x1, 24, sz1, "seat")
            cube(f"backrest_{row}_{side}", "seats", x0, 24, sz0, x1, 44, sz0 + 3, "seat")
            cube(f"headrest_{row}_{side}", "seats", x0 + 2, 44, sz0, x1 - 2, 48, sz0 + 3, "seat_light")
    cube("dash_top", "dash", -20, 34, 8, 20, TUB_TOP, 14, "dash")
    cube("binnacle", "dash", 3, TUB_TOP, 10, 15, 44, 14, "dash")
    dial(8.0, 41.0, 10.0, 2.2, "speed")
    dial(12.8, 41.0, 10.0, 1.5, "fuel")
    for i in range(8):
        a = 2 * math.pi * i / 8
        wx, wy = 8.5 + 4.6 * math.cos(a), 36 + 4.6 * math.sin(a)
        cube(f"wheel_rim_{i}", "steering", wx - 0.9, wy - 0.9, 4.0, wx + 0.9, wy + 0.9, 5.4, "seat")
    cube("column", "steering", 7.7, 32, 5, 9.3, 37, 10, "metal_dark")
    cube("gear_stick", "dash", -1, 17, -1, 1, 27, 1, "metal_dark")
    return list(CUBES)


def dial(x, y, z, radius, kind):
    """A dial facing the driver: a square plate a hair proud of the binnacle, painted round by radius and angle with its corners in the binnacle's tone; a red needle on the centre."""
    cube(f"dial_{kind}", f"dash/dial_{kind}", x - radius, y - radius, z - 0.4, x + radius, y + radius, z, "dash", decals={"back": "dial"})
    cube(f"needle_{kind}", f"dash/needle_{kind}", x - 0.25, y - 0.3, z - 0.9, x + 0.25, y + radius - 0.4, z - 0.6, "needle")


def wheel():
    CUBES.clear()
    # The tyre: eight slabs through the axle, each turned 22.5 degrees on from the last, whose long faces are the
    # sixteen facets of the tread; their widths shrink by a hair so their sidewalls do not fight.
    r = WHEEL_R
    facet = 2 * r * math.tan(math.pi / 16)
    for k in range(8):
        hw = WHEEL_W / 2 - 0.05 * k
        cube(f"tyre_{k}", "tyre", -hw, -r * math.cos(math.pi / 16), -facet / 2, hw, r * math.cos(math.pi / 16), facet / 2, "tyre",
             rotation=(22.5 * k, 0, 0), origin=(0, 0, 0), decals={"top": "tread", "bottom": "tread", "left": "rim", "right": "rim"})
    hr = 8.0
    hfacet = 2 * hr * math.tan(math.pi / 8)
    for k in range(4):
        hw = WHEEL_W / 2 + 0.4 - 0.05 * k
        cube(f"hub_{k}", "hub", -hw, -hr * math.cos(math.pi / 8), -hfacet / 2, hw, hr * math.cos(math.pi / 8), hfacet / 2, "metal_dark",
             rotation=(45 * k, 0, 0), origin=(0, 0, 0), decals={"left": "hubcap", "right": "hubcap"})
    return list(CUBES)


# ---------------------------------------------------------------- painting

def fill_noise(px, w, h, tones, seed, patch=3, lighter=0.14, darker=0.14):
    """Square patches, mostly the base tone, some lighter and a few darker: the calm speckle of a painted block model."""
    noise = Noise(seed)
    for y in range(0, h, patch):
        for x in range(0, w, patch):
            r = noise.next()
            tone = tones[1] if r < lighter else tones[2] if r > 1 - darker else tones[0]
            for dy in range(patch):
                for dx in range(patch):
                    if y + dy < h and x + dx < w:
                        px[y + dy][x + dx] = tone


def put(px, w, h, x, y, c):
    if 0 <= x < w and 0 <= y < h:
        px[y][x] = c


def paint(face, w, h, seed):
    """The texels of one face: its material's noise, then whatever the decal draws over it, by texel or by where the texel is."""
    tones = TONES[face.material]
    px = [[tones[0] for _ in range(w)] for _ in range(h)]
    if face.material == "body":
        fill_noise(px, w, h, tones, seed, patch=4, lighter=0.22, darker=0.05)
    else:
        fill_noise(px, w, h, tones, seed)
    base, light, dark = tones
    black = (14, 14, 16)
    decal = face.decal
    tl, tr, br, bl = face.corners
    du = sub(tr, tl)
    dv = sub(bl, tl)

    def world(i, j):
        return add(add(tl, scale(du, (i + 0.5) / w)), scale(dv, (j + 0.5) / h))

    # Bevels, the reference's signature: a light row along the top edge of every upright face and a dark row
    # along its bottom; on a top face, light along its front and side edges.
    if face.material in ("body", "rubber", "metal", "metal_dark") and h >= 3 and w >= 3:
        if face.direction == "up":
            for x in range(w):
                put(px, w, h, x, h - 1, light)
            for y in range(h):
                put(px, w, h, 0, y, light)
                put(px, w, h, w - 1, y, light)
        elif face.direction != "down":
            for x in range(w):
                put(px, w, h, x, 0, light)
                put(px, w, h, x, h - 1, dark)
    if decal == "grille":
        # seven slots two texels wide, a texel apart, centred, nearly the face's height; a texel of dark frame round them
        gw = 7 * 2 + 6
        x0 = w // 2 - gw // 2
        for y in range(1, h - 1):
            put(px, w, h, x0 - 1, y, dark)
            put(px, w, h, x0 + gw, y, dark)
        for x in range(x0 - 1, x0 + gw + 1):
            put(px, w, h, x, 1, dark)
            put(px, w, h, x, h - 2, dark)
        for k in range(7):
            for y in range(2, h - 2):
                put(px, w, h, x0 + k * 3, y, black)
                put(px, w, h, x0 + k * 3 + 1, y, black)
    elif decal == "lamp":
        # a rectangular lamp: a grey rim, three dark slats across a pale face
        for y in range(h):
            for x in range(w):
                rim = x == 0 or y == 0 or x == w - 1 or y == h - 1
                put(px, w, h, x, y, (150, 152, 158) if rim else (70, 72, 78) if y in (2, 4, 6) else light)
    elif decal == "hook":
        for y in range(h):
            for x in range(w):
                rim = x == 0 or y == 0 or x == w - 1 or y == h - 1
                put(px, w, h, x, y, dark if rim else black if y in (1, 3) else light)
    elif decal == "ring":
        cx, cy = (w - 1) / 2, (h - 1) / 2
        r = min(w, h) / 2
        for y in range(h):
            for x in range(w):
                d = math.hypot(x - cx, y - cy)
                put(px, w, h, x, y, light if r - 1.6 < d < r + 0.2 else (base if d <= r - 1.6 else dark))
    elif decal == "lens":
        cx, cy = (w - 1) / 2, (h - 1) / 2
        r = min(w, h) / 2
        for y in range(h):
            for x in range(w):
                d = math.hypot(x - cx, y - cy)
                c = base if d < r - 0.5 else (120, 124, 132)
                if d < r - 0.5 and x < cx and y < cy and d > r * 0.35:
                    c = light
                put(px, w, h, x, y, c)
        put(px, w, h, round(cx), round(cy), (255, 255, 240))
    elif decal == "bonnet":
        # four vent slots at the cowl end, placed by where the texel is: just ahead of the windshield's base
        rear = face.cube.lo[2]
        for j in range(h):
            for i in range(w):
                p = world(i, j)
                if 7.0 <= p[2] - rear < 9.0 and any(abs(p[0] - (-7.5 + k * 5)) < 2.0 for k in range(4)):
                    put(px, w, h, i, j, black)
    elif decal == "door":
        for x in range(w):
            put(px, w, h, x, 0, dark)
            put(px, w, h, x, h - 1, dark)
        for y in range(h):
            put(px, w, h, 0, y, dark)
            put(px, w, h, w - 1, y, dark)
        for x in range(2, w - 2):
            put(px, w, h, x, 3, light)
    elif decal == "flank":
        for x in range(w):
            put(px, w, h, x, 0, light)
    elif decal == "tailgate":
        for x in range(2, w - 2):
            put(px, w, h, x, 3, dark)
            put(px, w, h, x, h - 3, dark)
        for y in range(3, h - 2):
            put(px, w, h, 2, y, dark)
            put(px, w, h, w - 3, y, dark)
    elif decal == "bumper":
        # a highlight on top, the upper half plain, the lower half lighter, a shadow along the bottom
        for y in range(h):
            for x in range(w):
                put(px, w, h, x, y, light if y == 0 else base if y < h // 2 else light if y < h - 1 else dark)
    elif decal == "drum":
        for y in range(h):
            for x in range(w):
                rim = x == 0 or y == 0 or x == w - 1 or y == h - 1
                put(px, w, h, x, y, dark if rim else light)
    elif decal == "tail":
        for y in range(h):
            for x in range(w):
                put(px, w, h, x, y, dark if (x == 0 or y == 0 or x == w - 1 or y == h - 1) else base)
        put(px, w, h, 1, 1, light)
    elif decal == "glass":
        # nearly clear: a faint pane, one glare streak across it, a fine edge; the alpha rides with the texel
        for y in range(h):
            for x in range(w):
                edge = x == 0 or y == 0 or x == w - 1 or y == h - 1
                band = 0 <= (x + y) - (w // 3) <= 1
                put(px, w, h, x, y, light + (GLASS_STREAK,) if band else base + (GLASS_EDGE,) if edge else base + (GLASS_PANE,))
    elif decal == "mirror":
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                put(px, w, h, x, y, (200, 214, 226))
    elif decal == "dial":
        # by position in the dial's plane: the plate's centre is the cube's origin; round, the corners the binnacle's
        ox, oy, oz = face.cube.origin
        radius = (face.cube.hi[1] - face.cube.lo[1]) / 2
        for j in range(h):
            for i in range(w):
                p = world(i, j)
                d = math.hypot(p[0] - ox, p[1] - oy)
                ang = math.degrees(math.atan2(p[0] - ox, p[1] - oy))
                c = (30, 30, 34) if d < radius - 0.45 else (70, 72, 78) if d < radius else base
                if radius - 0.9 < d < radius - 0.45:
                    for k in range(9):
                        if abs(ang - (-120 + k * 30)) < 7:
                            c = (236, 232, 200)
                put(px, w, h, i, j, c)
    elif decal == "tread":
        # by angle round the axle: a block in the middle of each facet in two rows either side of a centre groove,
        # the rows staggered facet by facet, the shoulders plain
        for j in range(h):
            for i in range(w):
                p = sub(world(i, j), face.cube.origin)
                whole = math.degrees(math.atan2(p[2], p[1])) % 360
                k = int(whole // 22.5)
                ang = whole % 22.5
                row = 1 if p[0] > 0 else -1
                shift = 4.0 if (k + (row > 0)) % 2 == 0 else 6.5
                block = shift < ang < shift + 11.0 and 1.0 < abs(p[0]) < 4.4
                put(px, w, h, i, j, light if block else dark)
    elif decal == "rim":
        # by radius from the axle: sidewall, a rim ring, the rim face with five lugs, a hub
        hub = TONES["hub"]
        for j in range(h):
            for i in range(w):
                p = sub(world(i, j), face.cube.origin)
                d = math.hypot(p[1], p[2])
                ang = math.degrees(math.atan2(p[2], p[1]))
                if d > WHEEL_R - 0.7:
                    c = dark
                elif d > 11.0:
                    c = base
                elif d > 9.6:
                    c = hub[2]
                elif d > 7.2:
                    c = hub[0]
                    for k in range(6):
                        if abs(((ang - k * 60 + 180) % 360) - 180) < 11 and 7.4 < d < 9.4:
                            c = (60, 62, 68)
                else:
                    c = hub[1]
                put(px, w, h, i, j, c)
    elif decal == "hubcap":
        hub = TONES["hub"]
        for j in range(h):
            for i in range(w):
                p = sub(world(i, j), face.cube.origin)
                d = math.hypot(p[1], p[2])
                put(px, w, h, i, j, hub[1] if d < 2.4 else hub[0] if d < 5.6 else hub[2])
    return px


# ---------------------------------------------------------------- the atlas

def face_refs(cubes):
    refs = []
    for c in cubes:
        for d in DIRECTIONS:
            ref = FaceRef(c, d, c.faces.get(d, c.material), c.decals.get(d), c.corners(d))
            c.refs.append(ref)
            refs.append(ref)
    return refs


def layout(refs):
    """Gives every face a rect in the atlas at one texel per pixel (more where DETAIL says)."""
    for f in refs:
        tl, tr, br, bl = f.corners
        detail = DETAIL.get(f.decal, 1)
        f.rect = [max(1, round(length(sub(tr, tl)) * detail)), max(1, round(length(sub(bl, tl)) * detail))]
    order = sorted(range(len(refs)), key=lambda i: (-refs[i].rect[1], -refs[i].rect[0]))
    size = 256
    while True:
        x = y = shelf = 0
        ok = True
        for i in order:
            w, h = refs[i].rect[:2]
            if x + w + 1 > size:
                x, y, shelf = 0, y + shelf + 1, 0
            if y + h + 1 > size:
                ok = False
                break
            refs[i].rect = [w, h, x, y]
            x += w + 1
            shelf = max(shelf, h)
        if ok:
            return size
        size *= 2


def render_atlas(refs, size):
    px = [[(0, 0, 0, 0) for _ in range(size)] for _ in range(size)]
    for k, f in enumerate(refs):
        w, h, x0, y0 = f.rect
        alpha = ALPHA.get(f.material, 255)
        tex = paint(f, w, h, 7919 * k + 17)
        for y in range(h):
            for x in range(w):
                c = tex[y][x]
                px[y0 + y][x0 + x] = (c[0], c[1], c[2], c[3] if len(c) == 4 else alpha)
    return px


# ---------------------------------------------------------------- the project

def project(name, cubes, size, png):
    """A Blockbench project in the free format: the cubes, an outliner of folders, the one texture embedded."""
    elements = []
    for c in cubes:
        faces = {}
        for ref in c.refs:
            w, h, x0, y0 = ref.rect
            faces[ref.direction] = {"uv": [x0, y0, x0 + w, y0 + h], "texture": 0}
        elements.append({
            "name": c.name, "box_uv": False, "rescale": False, "locked": False, "light_emission": 0, "render_order": "default",
            "allow_mirror_modeling": True, "from": list(c.lo), "to": list(c.hi), "autouv": 0, "color": 0,
            "origin": list(c.origin), "rotation": list(c.rotation), "faces": faces, "type": "cube", "uuid": c.uuid,
        })
    root = []
    folders = {}

    def folder(path):
        if path in folders:
            return folders[path]
        node = {"name": path.split("/")[-1], "origin": [0, 0, 0], "color": 0, "uuid": str(uuidlib.uuid5(uuidlib.NAMESPACE_URL, name + "/" + path)),
                "export": True, "mirror_uv": False, "isOpen": False, "locked": False, "visibility": True, "autouv": 0, "children": []}
        folders[path] = node
        parent = path.rsplit("/", 1)[0] if "/" in path else None
        (folder(parent)["children"] if parent else root).append(node)
        return node

    for c in cubes:
        folder(c.folder)["children"].append(c.uuid)
    texture = {
        "path": "", "name": f"{name}.png", "folder": "", "namespace": "", "id": "0", "width": size, "height": size,
        "uv_width": size, "uv_height": size, "particle": False, "render_mode": "default", "render_sides": "auto",
        "frame_time": 1, "frame_order_type": "loop", "frame_order": "", "frame_interpolate": False, "visible": True,
        "internal": True, "saved": False, "uuid": str(uuidlib.uuid5(uuidlib.NAMESPACE_URL, name + "/texture")),
        "relative_path": "", "source": "data:image/png;base64," + base64.b64encode(png).decode("ascii"),
    }
    return {
        "meta": {"format_version": "4.10", "model_format": "free", "box_uv": False},
        "name": name, "model_identifier": "", "visible_box": [1, 1, 0], "variable_placeholders": "", "variable_placeholder_buttons": [],
        "unhandled_root_fields": {}, "resolution": {"width": size, "height": size},
        "elements": elements, "outliner": root, "textures": [texture],
    }


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def build(name, cubes):
    refs = face_refs(cubes)
    size = layout(refs)
    png = png_bytes(size, size, render_atlas(refs, size))
    write_json(ASSETS / f"vanillawheels/mesh/{name}.bbmodel", project(name, cubes, size, png))
    return len(cubes), size


# ---------------------------------------------------------------- the profile

# A rider's camera sits 1.02 blocks (16 px) above the seat point: the player's vehicle attachment is
# 0.6 below it and the eye 1.62 above that. The eye lands at 46, over the binnacle and under the header.
SEAT_Y = 30
SPEED_PIVOT = [8.0, 41.0, 9.6]
FUEL_PIVOT = [12.8, 41.0, 9.6]


def profile():
    return {
        "mesh": "trailblazer:trailblazer",
        "wheel_mesh": "trailblazer:trailblazer_wheel",
        "scale": 0.0625,
        "handedness": "right",
        "body": {"width": 2.75, "length": 6.9, "height": 3.5,
                 "parts": [{"at": [0, 10, 35], "width": 3.4, "height": 1.5}, {"at": [0, 10, -36], "width": 3.4, "height": 1.5}]},
        "seats": [{"at": [8, SEAT_Y, 1], "driver": True}, {"at": [-8, SEAT_Y, 1]}, {"at": [8, SEAT_Y, -18]}, {"at": [-8, SEAT_Y, -18]}],
        "wheels": {"radius": WHEEL_R, "positions": [{"forward": FRONT_AXLE, "right": -TRACK, "steers": True}, {"forward": FRONT_AXLE, "right": TRACK, "steers": True},
                                                   {"forward": REAR_AXLE, "right": -TRACK}, {"forward": REAR_AXLE, "right": TRACK}]},
        "engine": {"max_speed": 0.9, "acceleration": 0.02, "reverse_speed": 0.3, "brake": 0.05, "drag": 0.01},
        "handling": {"grip": 0.85, "steer_degrees": 32, "drift_grip": 0.12, "drift_boost": 0.3, "drift_charge_ticks": 40},
        "climb": 2.0,
        "mass": 1.45,
        "fuel": {"capacity": 24000},
        "storage": {"rows": 6, "region": {"z_max": -26}, "chest": {"at": [0, 16, -42], "yaw": 180}},
        # The dials face the driver (-z); needles point up at rest. Seen by the driver, positive about +z is
        # clockwise, so both sweep clockwise from eight o'clock (-120 degrees) through four (+120).
        "gauges": [{"kind": "speed", "part": {"group": "needle_speed"}, "pivot": SPEED_PIVOT, "axis": [0, 0, 1], "zero": -2.094, "sweep": 4.189},
                   {"kind": "fuel", "part": {"group": "needle_fuel"}, "pivot": FUEL_PIVOT, "axis": [0, 0, 1], "zero": -2.094, "sweep": 4.189}],
        "headlights": {"at": [[15, 32.5, 47.5], [-15, 32.5, 47.5]], "part": {"group": "lenses"}, "range": 10},
        "horn": "vanillawheels:horn.truck",
        "radio": {"at": [-4, 37, 12]},
        "hitch": {"rear": [0, 21, -60]},
        "paint": {"part": {"group": "body"}, "default": "light_blue"},
        "glass": {"group": "windshield"},
        "sounds": {"engine": "vanillawheels:engine.petrol"},
    }


LIGHT_BLUE = tuple(round(c + (255 - c) * 0.25) for c in (58, 179, 218))  # the dye, lifted as Vanilla Wheels lifts every paint


def preview(truck_cubes, wheel_cubes, wheel_slots):
    """
    A project for looking at, never shipped: the truck with its four wheels
    in place and the body tinted as the light-blue dye tints it in the
    game, so Blockbench shows what a player sees. Written under
    devtools/art/preview/.
    """
    cubes = list(truck_cubes)
    for k, (forward, right) in enumerate(wheel_slots):
        for w in wheel_cubes:
            side = "right" if right > 0 else "left"
            dx, dy, dz = -right, WHEEL_R, forward
            c = Cube(f"{w.name}_{k}", f"wheels/wheel_{k}_{side}", add(w.lo, (dx, dy, dz)), add(w.hi, (dx, dy, dz)), w.material,
                     w.rotation, add(w.origin, (dx, dy, dz)), dict(w.faces), dict(w.decals))
            cubes.append(c)
    refs = face_refs(cubes)
    size = layout(refs)
    px = render_atlas(refs, size)
    for f in refs:
        if f.material == "body":
            w, h, x0, y0 = f.rect
            for y in range(y0, y0 + h):
                for x in range(x0, x0 + w):
                    r, g, b, a = px[y][x]
                    px[y][x] = (r * LIGHT_BLUE[0] // 255, g * LIGHT_BLUE[1] // 255, b * LIGHT_BLUE[2] // 255, a)
    out = ROOT / "devtools/art/preview/trailblazer_preview.bbmodel"
    write_json(out, project("trailblazer_preview", cubes, size, png_bytes(size, size, px)))
    return out


def main(argv) -> None:
    n, size = build("trailblazer", truck())
    truck_cubes = list(CUBES)
    wn, wsize = build("trailblazer_wheel", wheel())
    wheel_cubes = list(CUBES)
    slots = [(w["forward"], w["right"]) for w in profile()["wheels"]["positions"]]
    print("preview:", preview(truck_cubes, wheel_cubes, slots))
    write_json(DATA / "vanillawheels/vehicle/trailblazer.json", profile())
    write_json(ASSETS / "lang/en_us.json", {"vehicle.trailblazer.trailblazer": "Trailblazer"})
    for stale in ("trailblazer.obj", "trailblazer_wheel.obj"):
        (ASSETS / "vanillawheels/mesh" / stale).unlink(missing_ok=True)
    (ASSETS / "textures/entity/trailblazer.png").unlink(missing_ok=True)
    print(f"wrote the truck ({n} cubes, a {size} atlas), the wheel ({wn} cubes, a {wsize} atlas), the profile")


if __name__ == "__main__":
    main(sys.argv)
