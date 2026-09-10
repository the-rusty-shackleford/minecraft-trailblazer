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
recipe and a lang file, with the protocol nested inside. Everything shipped is written
by `devtools/art/build.py`, which designs the truck as cubes to Rusty's reference image
and paints every face; a preview project with the wheels on and the paint tinted is
written under `devtools/art/preview/` for looking at in Blockbench.

## Shape

No Java in the mod. `gametest` is a mod of its own: six gametests and a photo booth. The
pipeline is the only code: the cube list (tub, doors, bonnet and nose, fenders, bumpers,
the raked windshield frame and the cage, mirrors, seats, dash and dials, steering
wheel; the wheel as eight tyre slabs and four hub slabs), a shelf-packed atlas at a texel
a pixel (four on the dials), decals painted per face or by world position, the Blockbench
project writer, and the profile as a Python dict sharing the cubes' constants.

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
(2026-09-09): the Blockbench truck. 1.2.0 (2026-09-09): the truck matched to the
reference part by part from side-by-side frames -- Rusty's bar is the exterior exactly
as the reference's, four doors and the chest the only differences -- with the
protocol's inside-out lighting fixed on the way (Vanilla Wheels 1.3.1). Rusty's friend
made a pass in Blockbench too (fenders down onto the tyres, angled arch ends, a chest
modelled in the bed), all of which the rebuilt model already has. Next: the tuning
session -- top speed, drift, damage, the dial size and the seat position are numbers to
watch, not to plan.
