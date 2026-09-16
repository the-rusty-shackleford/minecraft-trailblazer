---
title: Trailblazer — project
type: overview
layer: store
tags: [overview]
---

# Trailblazer

## What this is

The first vehicle for Vanilla Wheels: a data-only NeoForge 1.21.1 mod (`lowcodefml`)
holding a profile, two Blockbench projects (the body and a wheel, textures embedded), a
recipe and a lang file, with the protocol nested inside. The truck is the hand-built
project `devtools/art/preview/trailblazer.bbmodel`; everything shipped is written from it
by `devtools/art/adopt.py` (D-0003).

## Shape

No Java in the mod. `gametest` is a mod of its own: eleven gametests, a photo booth and the
playtest. `adopt.py` is the only pipeline: it splits the project by folder, divides the
body's texels by the preview's tint, moves the wheel to its axle, and writes the profile
off the cubes.

## How it is verified

Looking first: renders of the preview through Blockbench's own camera (driven over its
remote-debugging port) from five angles and close on every joint, compared with the
reference. Then `./gradlew check`: eleven gametests (profile, speed and the one-block step, four hillsides of one-block risers, the two-block wall,
running a cow over, the gas can, the chassis recipe, the radio) and the booth under the pack's
shaders (side stock and red, windshield and dash from the driver's seat at speed, the
quarters, lamps at night from behind and in front with the beam on the ground).

## Decisions

D-0001 (superseded): the generator's bundle repaired by a scripted edit. D-0002: the
truck is designed as a Blockbench project in code, to the reference, and reviewed as
renders before any booth; the bundle is gone.

## Next

1.0.0 (2026-09-09): the repaired bundle, which Rusty called the Temu version. 1.1.0
(2026-09-09): the Blockbench truck from the generator. 1.2.0 (2026-09-09): matched to the
reference part by part from side-by-side frames, the protocol's inside-out lighting fixed
on the way. 1.3.0 (2026-09-10, pack 1.30.0): Rusty's friend rebuilt the wheels in
Blockbench -- twelve tread blocks and a rim plate, the reference's own construction --
and lowered the fenders onto them, and it was plainly better than the generator's painted
slabs; his file is the source as it is (D-0003), split by `adopt.py`, with the protocol
reading Blockbench 5's groups list and a factory paint colour so the game shows the
preview's blue, and one glare on the windshield. Rusty's reference image and the friend's
file as received are kept outside the repo at `/home/rusty/Code/minecraft mods/tools/reference/`.
Any change to the truck is made in Blockbench and adopted; nothing generates it.

1.4.0 (2026-09-10): the friend's file replaced by Rusty's rescaled one (4.64 long, 2.65
tall, a size a player fits), `adopt.py` made scale-free (seats, hit boxes, the collision
box as the hull, the chest's scale, the hitch and radio all read off the cubes; D-0003
written down), nesting Vanilla Wheels 1.5.0 (its D-0007: the playtest's findings), and the
playtest itself: `TrailblazerPlaytest`, one course driven by the truck from behind and
from the driver's eyes and by an Automobility motorcar, plus a side-on climb with a
villager aboard.

1.5.0 (2026-09-13): nfx's V4 is the truck (headrests gone, the chest modelled in the bed,
no vanilla chest drawn), his seat placement (cushion top + 0.4 units), `climb` 1.0, on the
library with his pose ported (VW D-0008); the eye, cockpit and rider scale dropped from the
profile on Rusty's call for nfx's view.

Next: the tuning session -- top speed, drift, run-over damage, the dial size and the seat
position are numbers to watch in the booth with Rusty, not to plan.

2026-09-16, held work verified: the old course prematurely ended drift and left the
rugged weave before the pad. D-0004 repairs the harness and pins completion. All four
Trailblazer runs then completed release and forty boost ticks at up to 1.158 blocks/tick;
no stuck reports or server move rejections. The rough course median was 0.891 blocks/tick,
with no ignored steering while grounded. Existing tuning, client authority, server
collision and nfx’s supplied model remain unchanged. Subjective speed, drift, rider and
dashboard preferences remain Rusty’s review of the captured baseline; releases stay held.

The shader photo booth passed all twelve visual/seat/light assertions and its final
completion marker after separating shaded body hue from bright dashboard needles.
The malformed run selection `terrain,` was rejected by the real client and Gradle
with a nonzero exit, as intended. Both the focused valid weave and final complete five-run comparison passed the same
gate; the final comparison reproduced the recorded metrics exactly.
