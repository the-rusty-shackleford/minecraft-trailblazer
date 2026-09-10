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

# Three tones each: base, light, dark. The body's are greys the paint multiplies into: the profile's factory
# colour, the reference's own blue, until a dye replaces it. The base sits high so the blue keeps its headroom
# under the shaders, the mottle a step either side of it.
TONES = {
    "body": ((226, 226, 226), (255, 255, 255), (196, 196, 196)),
    "rubber": ((36, 38, 44), (58, 60, 66), (24, 26, 30)),
    "tyre": ((40, 42, 46), (104, 106, 112), (26, 28, 30)),
    "metal": ((174, 178, 186), (206, 210, 218), (138, 142, 150)),
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
GLASS_PANE, GLASS_EDGE, GLASS_STREAK = 50, 110, 190
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

WHEEL_R = 16.5
WHEEL_W = 11.0
FRONT_AXLE = 36
REAR_AXLE = -45
TRACK = 22
# The body's datum lines, measured off the reference against its tub: the tyres seven tenths of the tub's height
# across, the bed sides' top edge and the raised bonnet's top a fifth of a tyre over the tyre's top, the fenders'
# tops two pixels under that, hugging the tyre, the cage's top eighteen pixels over the tub. The wheelbase is
# the one thing that is not the reference's: it is longer by a rear door.
TUB_TOP = 40
HOOD_TOP = 40
FENDER_TOP = 37
FENDER_T = 3
CAGE_TOP = 61
NOSE = 50
TAIL = -60
HOOP = -28


def truck():
    CUBES.clear()
    B = "body"
    # --- the tub: floor, sides, tailgate; the doors as panels a pixel proud of the sides with a seam painted
    # round them; a marker lamp on each front corner
    cube("floor", "tub", -18, 12, TAIL + 2, 18, 16, 16, "floor")
    cube("side_left", "body/tub", 18, 16, TAIL, 21, TUB_TOP, 16, B, decals={"left": "flank"})
    cube("side_right", "body/tub", -21, 16, TAIL, -18, TUB_TOP, 16, B, decals={"right": "flank"})
    cube("tailgate", "body/tub", -21, 16, TAIL, 21, TUB_TOP, TAIL + 2, B, decals={"back": "tailgate"})
    cube("tail_sill", "body/tub", -21, 12, TAIL, 21, 16, TAIL + 2, B)
    for sx, side in ((1, "left"), (-1, "right")):
        x0, x1 = (21, 22) if sx > 0 else (-22, -21)
        cube(f"door_front_{side}", "body/doors", x0, 20, -6, x1, TUB_TOP - 1, 10, B, decals={side: "door"})
        cube(f"door_rear_{side}", "body/doors", x0, 20, -26, x1, TUB_TOP - 1, -10, B, decals={side: "door"})
        hx0, hx1 = (22, 23) if sx > 0 else (-23, -22)
        cube(f"handle_front_{side}", "handles", hx0, 31, 5, hx1, 32, 9, "metal")
        cube(f"handle_rear_{side}", "handles", hx0, 31, -15, hx1, 32, -11, "metal")
        mx0, mx1 = (17, 20) if sx > 0 else (-20, -17)
        cube(f"marker_{side}", "lights", mx0, 23, NOSE, mx1, 25.5, NOSE + 0.5, "metal")
    # --- the bonnet: a raised slab a pixel in from the body's sides, its vents at the cowl end; the engine bay
    # under it; the nose a slab whose face is the grille, the lamps proud of it at its top corners; the cowl
    # behind the bonnet, which the windshield's base rail sits on
    cube("bonnet", "body/bonnet", -19, HOOD_TOP - 3, 16, 19, HOOD_TOP, NOSE - 1, B, decals={"top": "bonnet"})
    cube("engine_bay", "body/bonnet", -20, 16, 16, 20, HOOD_TOP - 3, NOSE - 2, B)
    cube("nose", "body/bonnet", -20, 16, NOSE - 2, 20, HOOD_TOP - 2, NOSE, B, decals={"front": "grille"})
    cube("cowl", "body/bonnet", -20, 34, 8, 20, HOOD_TOP - 2, 16, B)
    for sx, side in ((1, "left"), (-1, "right")):
        x0, x1 = (12, 18) if sx > 0 else (-18, -12)
        cube(f"lens_{side}", "lamps/lenses", x0, 30, NOSE, x1, 37, NOSE + 1, "lamp", decals={"front": "lamp"})
    # --- fenders: black shells three pixels thick, each a flat top over the wheel with a slope angled down at
    # each end -- the front fender's nose slope runs down to the bumper and a block fills below it beside the
    # grille; its rear slope ends ahead of the front door and a leg drops from there to the rocker; the rear
    # fender mirrors it. The rocker step between the legs.
    for sx, side in ((1, "left"), (-1, "right")):
        x0, x1 = (20, 25) if sx > 0 else (-25, -20)
        fx = (x0 + x1) / 2
        lx0, lx1 = (x1 - 3, x1) if sx > 0 else (x0, x0 + 3)
        top = FENDER_TOP
        bot = FENDER_TOP - FENDER_T
        # front
        cube(f"fender_front_{side}", "fenders", x0, bot, 22, x1, top, NOSE - 2, "rubber")
        cube(f"fender_front_nose_{side}", "fenders", x0, bot, NOSE - 2, x1, top, NOSE + 12, "rubber", rotation=(38, 0, 0), origin=(fx, top, NOSE - 2))
        cube(f"fender_front_block_{side}", "fenders", x0, 16, NOSE + 4, x1, 29, NOSE + 8, "rubber")
        cube(f"fender_front_tail_{side}", "fenders", x0, bot, 12, x1, top, 22, "rubber", rotation=(-45, 0, 0), origin=(fx, top, 22))
        cube(f"fender_front_leg_{side}", "fenders", lx0, 15, 12, lx1, 32, 15, "rubber")
        # rear
        cube(f"fender_rear_{side}", "fenders", x0, bot, -58, x1, top, -32, "rubber")
        cube(f"fender_rear_nose_{side}", "fenders", x0, bot, -32, x1, top, -22, "rubber", rotation=(45, 0, 0), origin=(fx, top, -32))
        cube(f"fender_rear_leg_{side}", "fenders", lx0, 15, -28, lx1, 32, -25, "rubber")
        cube(f"fender_rear_tail_{side}", "fenders", x0, bot, -66, x1, top, -58, "rubber", rotation=(-45, 0, 0), origin=(fx, top, -58))
        cube(f"fender_rear_block_{side}", "fenders", x0, 16, -64, x1, 31, -60, "rubber")
        sx0, sx1 = (21, 25) if sx > 0 else (-25, -21)
        cube(f"step_{side}", "fenders", sx0, 12, -25, sx1, 15, 12, "floor")
    # --- bumpers, deep, with chamfered ends; hook lamps and a winch on the front one, the hitch ball on the rear
    BUMPER = (8, 16)
    cube("bumper_front", "bumpers", -25, BUMPER[0], NOSE, 25, BUMPER[1], NOSE + 12, "metal", decals={"front": "bumper"})
    cube("bumper_rear", "bumpers", -25, BUMPER[0], TAIL - 6, 25, BUMPER[1], TAIL, "metal", decals={"back": "bumper"})
    for sx, side in ((1, "left"), (-1, "right")):
        x0, x1 = (25, 31) if sx > 0 else (-31, -25)
        cube(f"bumper_end_front_{side}", "bumpers", x0, BUMPER[0], NOSE, x1, BUMPER[1], NOSE + 12, "metal", rotation=(0, 32 * sx, 0), origin=(25 * sx, 10, NOSE + 6), decals={"front": "bumper"})
        cube(f"bumper_end_rear_{side}", "bumpers", x0, BUMPER[0], TAIL - 6, x1, BUMPER[1], TAIL, "metal", rotation=(0, -32 * sx, 0), origin=(25 * sx, 10, TAIL - 3), decals={"back": "bumper"})
        fx0, fx1 = (18, 23) if sx > 0 else (-23, -18)
        cube(f"hook_lamp_{side}", "bumpers", fx0, BUMPER[1], NOSE + 7, fx1, BUMPER[1] + 7, NOSE + 11, "metal", decals={"front": "hook"})
    cube("winch", "bumpers", -7, BUMPER[1], NOSE + 5, 7, BUMPER[1] + 8, NOSE + 10, "metal_dark")
    cube("winch_drum", "bumpers", -3, BUMPER[1] + 1, NOSE + 10, 3, BUMPER[1] + 7, NOSE + 11, "metal", decals={"front": "drum"})
    cube("winch_cable", "bumpers", -0.5, BUMPER[0] + 4, NOSE + 11, 0.5, BUMPER[1] + 1, NOSE + 12, "metal_dark")
    cube("winch_hook", "bumpers", -1.5, BUMPER[0] + 1, NOSE + 10.5, 1.5, BUMPER[0] + 4, NOSE + 12.5, "metal_dark")
    cube("hitch_post", "bumpers", -1, BUMPER[1], TAIL - 7, 1, 20, TAIL - 4, "metal_dark")
    cube("hitch_ball", "bumpers", -2, 20, TAIL - 8, 2, 22, TAIL - 4, "metal")
    for sx, side in ((1, "left"), (-1, "right")):
        x0, x1 = (13, 19) if sx > 0 else (-19, -13)
        cube(f"tail_light_{side}", "lights", x0, 28, TAIL - 1, x1, 34, TAIL, "tail", decals={"back": "tail"})
    cube("exhaust", "bumpers", 9, 11, TAIL - 4, 11, 13, TAIL + 8, "metal_dark")
    # --- the windshield: one raked frame -- base rail, two pillars -- turned together about the base's
    # centreline, the glass inset in it, all running up into a level header that is one bar with the cage.
    # A turn about +X by a positive angle carries the top toward +Z, the nose: a windshield leans back, so its
    # rake is negative. The base rail starts down inside the bonnet and cowl so that, turned, no edge of it
    # lifts clear of them. The pillars are a pixel thinner than the cage's bars, as the reference's are.
    T = 4
    P = 3
    RAKE = -14
    PIVOT = (0, 40, 14)
    cube("windshield_base", "cage/windshield_frame", -21, 36, 12, 21, 41, 16, "metal", rotation=(RAKE, 0, 0), origin=PIVOT)
    for sx, side in ((1, "left"), (-1, "right")):
        x0, x1 = (18, 18 + P) if sx > 0 else (-18 - P, -18)
        cube(f"a_pillar_{side}", "cage/windshield_frame", x0, 41, 12.5, x1, CAGE_TOP - 1, 15.5, "metal", rotation=(RAKE, 0, 0), origin=PIVOT)
    cube("windshield", "windshield", -18, 41, 13.75, 18, CAGE_TOP - T + 1, 14.25, "glass", rotation=(RAKE, 0, 0), origin=PIVOT, decals={"front": "glass", "back": "glass"})
    pillar_rear = rotate((0, CAGE_TOP - T, 12.5), PIVOT, (RAKE, 0, 0))[2]
    pillar_front = rotate((0, CAGE_TOP - 1, 15.5), PIVOT, (RAKE, 0, 0))[2]
    header_back = math.floor(pillar_rear - 0.5)
    header_front = round(pillar_front, 2)
    cube("header", "cage/windshield_frame", -21, CAGE_TOP - T, header_back, 21, CAGE_TOP, header_front, "metal")
    # --- the cage: a flat rectangle over the front seats; at its rear corners an A-frame pair each side, one
    # post straight down to the tub and one leaning forward to it, as the reference's
    for sx, side in ((1, "left"), (-1, "right")):
        x0, x1 = (17, 17 + T) if sx > 0 else (-17 - T, -17)
        cube(f"roof_rail_{side}", "cage", x0, CAGE_TOP - T, HOOP, x1, CAGE_TOP, header_back + 0.5, "metal")
        cube(f"hoop_post_{side}", "cage", x0, TUB_TOP, HOOP, x1, CAGE_TOP - T, HOOP + T, "metal")
        # The A's second leg: from the same top corner as the post, turned thirty degrees about it so its foot
        # lands on the tub's top edge about twelve pixels ahead; long enough that, turned, the foot sits a pixel
        # down inside the side rather than lifting off it.
        LEAN = 30
        drop = (CAGE_TOP - T) - (TUB_TOP - 1.0)
        cube(f"lean_post_{side}", "cage", x0, CAGE_TOP - T - drop / math.cos(math.radians(LEAN)), HOOP, x1, CAGE_TOP - T, HOOP + T, "metal",
             rotation=(LEAN, 0, 0), origin=((x0 + x1) / 2, CAGE_TOP - T, HOOP + T / 2))
    cube("hoop_bar", "cage", -21, CAGE_TOP - T, HOOP, 21, CAGE_TOP, HOOP + T, "metal")
    # --- mirrors on the pillars
    for sx, side in ((1, "left"), (-1, "right")):
        ax0, ax1 = (21, 27) if sx > 0 else (-27, -21)
        mx0, mx1 = (23, 29) if sx > 0 else (-29, -23)
        cube(f"mirror_arm_{side}", "mirrors", ax0, 44, 12.5, ax1, 45, 13.5, "metal_dark")
        cube(f"mirror_{side}", "mirrors", mx0, 40, 11.5, mx1, 50, 13.5, "metal", decals={"back": "mirror"})
    # --- inside: seats, dash, binnacle with the dials, steering wheel, gear stick
    for row, (sz0, sz1) in (("front", (-5, 7)), ("rear", (-35, -23))):
        for sx, side in ((1, "left"), (-1, "right")):
            x0, x1 = (3, 14) if sx > 0 else (-14, -3)
            cube(f"cushion_{row}_{side}", "seats", x0, 17, sz0, x1, 24, sz1, "seat")
            cube(f"backrest_{row}_{side}", "seats", x0, 24, sz0, x1, 46, sz0 + 3, "seat")
            cube(f"headrest_{row}_{side}", "seats", x0 + 1, 46, sz0, x1 - 1, 51, sz0 + 3, "seat_light")
    cube("dash_top", "dash", -20, 34, 8, 20, 38, 14, "dash")
    cube("binnacle", "dash", 3, 38, 10, 15, 44, 14, "dash")
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

def fill_noise(px, w, h, tones, seed, patch=3, lighter=0.14, darker=0.14, keep=False):
    """Square patches, mostly the base tone, some lighter and a few darker: the calm speckle of a painted block model.
    With keep, the base-tone patches leave what is under them alone, so a second pass layers on a first."""
    noise = Noise(seed)
    for y in range(0, h, patch):
        for x in range(0, w, patch):
            r = noise.next()
            tone = tones[1] if r < lighter else tones[2] if r > 1 - darker else None if keep else tones[0]
            if tone is None:
                continue
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
    if face.material == "rubber" and face.direction == "up":
        tones = (tones[1], (70, 72, 80), tones[0])
    px = [[tones[0] for _ in range(w)] for _ in range(h)]
    if face.material == "body":
        fill_noise(px, w, h, tones, seed, patch=4, lighter=0.18, darker=0.04)
        fill_noise(px, w, h, tones, seed + 1, patch=2, lighter=0.06, darker=0.0, keep=True)
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
        # seven slots two texels wide, a texel apart, centred, from two rows under the bonnet's edge to two above
        # the bumper, their top corners knocked off; a texel of dark frame round them
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
            put(px, w, h, x0 + k * 3, 2, dark)
            put(px, w, h, x0 + k * 3 + 1, 2, dark)
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
                put(px, w, h, x, y, dark if rim else black if y in (2, 4) else light)
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
        # a highlight on top, a groove between two tiers, a shadow along the bottom
        for y in range(h):
            for x in range(w):
                put(px, w, h, x, y, light if y == 0 else dark if y == h // 2 else dark if y == h - 1 else base)
    elif decal == "drum":
        # the winch's face plate: light, a dark square at its centre
        for y in range(h):
            for x in range(w):
                centre = abs(x - (w - 1) / 2) < 1.0 and abs(y - (h - 1) / 2) < 1.0
                put(px, w, h, x, y, (60, 62, 68) if centre else light)
    elif decal == "tail":
        for y in range(h):
            for x in range(w):
                put(px, w, h, x, y, dark if (x == 0 or y == 0 or x == w - 1 or y == h - 1) else base)
        put(px, w, h, 1, 1, light)
    elif decal == "glass":
        # nearly clear: a faint pane, a fine edge, and the reference's glare -- a thin white bracket in the top-left
        # and bottom-right corners; the alpha rides with the texel
        white = (244, 248, 252)
        for y in range(h):
            for x in range(w):
                edge = x == 0 or y == 0 or x == w - 1 or y == h - 1
                bracket = (2 <= x <= 6 and y == 2) or (x == 2 and 2 <= y <= 5) or (w - 7 <= x <= w - 3 and y == h - 3) or (x == w - 3 and h - 6 <= y <= h - 3)
                put(px, w, h, x, y, white + (GLASS_STREAK,) if bracket else base + (GLASS_EDGE,) if edge else base + (GLASS_PANE,))
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
                shift = 1.5 if (k + (row > 0)) % 2 == 0 else 4.0
                block = shift < ang < shift + 16.0 and 1.0 < abs(p[0]) < 4.9
                put(px, w, h, i, j, light if block else dark)
    elif decal == "rim":
        # by radius from the axle: the sidewall, the tread's blocks wrapping a texel onto the shoulder, a light
        # lip, a dark dish with six light spokes; the hub's cubes take over inside
        hub = TONES["hub"]
        for j in range(h):
            for i in range(w):
                p = sub(world(i, j), face.cube.origin)
                d = math.hypot(p[1], p[2])
                ang = math.degrees(math.atan2(p[2], p[1]))
                if d > WHEEL_R - 0.7:
                    c = dark
                elif d > WHEEL_R - 2.2:
                    c = light if int(((ang + 180) % 360) // 11.25) % 2 == 0 else dark
                elif d > 11.0:
                    c = base
                elif d > 9.8:
                    c = hub[0]
                else:
                    c = (58, 60, 66)
                    for k in range(6):
                        if abs(((ang - k * 60 + 180) % 360) - 180) < 8:
                            c = hub[0]
                put(px, w, h, i, j, c)
    elif decal == "hubcap":
        # a light ring, a dark ring, a light cap with a dark square at its centre
        hub = TONES["hub"]
        for j in range(h):
            for i in range(w):
                p = sub(world(i, j), face.cube.origin)
                d = math.hypot(p[1], p[2])
                sq = max(abs(p[1]), abs(p[2]))
                put(px, w, h, i, j, (40, 42, 46) if sq < 1.5 else hub[1] if d < 3.6 else (56, 58, 64) if d < 5.8 else hub[0])
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
        "body": {"width": 2.75, "length": 8.0, "height": 3.7,
                 "parts": [{"at": [0, 10, 38], "width": 3.4, "height": 1.5}, {"at": [0, 10, -45], "width": 3.4, "height": 1.5}]},
        "seats": [{"at": [8, SEAT_Y, 1], "driver": True}, {"at": [-8, SEAT_Y, 1]}, {"at": [8, SEAT_Y, -29]}, {"at": [-8, SEAT_Y, -29]}],
        "wheels": {"radius": WHEEL_R, "positions": [{"forward": FRONT_AXLE, "right": -TRACK, "steers": True}, {"forward": FRONT_AXLE, "right": TRACK, "steers": True},
                                                   {"forward": REAR_AXLE, "right": -TRACK}, {"forward": REAR_AXLE, "right": TRACK}]},
        "engine": {"max_speed": 0.9, "acceleration": 0.02, "reverse_speed": 0.3, "brake": 0.05, "drag": 0.01},
        "handling": {"grip": 0.85, "steer_degrees": 32, "drift_grip": 0.12, "drift_boost": 0.3, "drift_charge_ticks": 40},
        "climb": 2.0,
        "mass": 1.45,
        "fuel": {"capacity": 24000},
        "storage": {"rows": 6, "region": {"z_max": -38}, "chest": {"at": [0, 16, -52], "yaw": 180}},
        # The dials face the driver (-z); needles point up at rest. Seen by the driver, positive about +z is
        # clockwise, so both sweep clockwise from eight o'clock (-120 degrees) through four (+120).
        "gauges": [{"kind": "speed", "part": {"group": "needle_speed"}, "pivot": SPEED_PIVOT, "axis": [0, 0, 1], "zero": -2.094, "sweep": 4.189},
                   {"kind": "fuel", "part": {"group": "needle_fuel"}, "pivot": FUEL_PIVOT, "axis": [0, 0, 1], "zero": -2.094, "sweep": 4.189}],
        "headlights": {"at": [[15.5, 33.5, NOSE + 1.5], [-15.5, 33.5, NOSE + 1.5]], "part": {"group": "lenses"}, "range": 10},
        "horn": "vanillawheels:horn.truck",
        "radio": {"at": [-4, 37, 12]},
        "hitch": {"rear": [0, 21, -68]},
        # The factory colour is the reference's blue as the shaders render it, tuned by measuring a booth frame's
        # hood against the reference image; light blue is the dye a repaint falls back to.
        "paint": {"part": {"group": "body"}, "default": "light_blue", "factory": FACTORY},
        "glass": {"group": "windshield"},
        "sounds": {"engine": "vanillawheels:engine.petrol"},
    }


FACTORY = "#58acff"
LIGHT_BLUE = tuple(int(FACTORY[i:i + 2], 16) for i in (1, 3, 5))  # the factory colour, what an undyed truck wears


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
