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

No Java in the mod. `gametest` is a mod of its own: six gametests, a photo booth and the
playtest. `adopt.py` is the only pipeline: it splits the project by folder, divides the
body's texels by the preview's tint, moves the wheel to its axle, and writes the profile
off the cubes.

## How it is verified

Looking first: renders of the preview through Blockbench's own camera (driven over its
remote-debugging port) from five angles and close on every joint, compared with the
reference. Then `./gradlew check`: six gametests (profile, speed and the two-block step,
running a cow over, coal, the chassis recipe, the radio) and the booth under the pack's
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

Next: the tuning session -- top speed, drift, run-over damage, the dial size and the seat
position are numbers to watch in the booth with Rusty, not to plan.
