---
title: Trailblazer — project
type: overview
layer: store
tags: [overview]
---

# Trailblazer

## What this is

The first vehicle for Vanilla Wheels: a data-only NeoForge 1.21.1 mod (`lowcodefml`)
holding a profile, two OBJ meshes, a texture, a recipe and a lang file, with the protocol
nested inside. The generator's bundle is committed under `devtools/art/src/`; everything
shipped is written by `devtools/art/build.py`.

## Shape

No Java in the mod. `gametest` is a mod of its own: six gametests and a photo booth. The
pipeline is the only code: a piece-wise editor over the bundle's boxes (hollow the cab,
raise the roof, move the cluster, replace the needles, move the wheel), a UV rewriter, an
atlas generator, and the profile as a Python dict.

## How it is verified

`./gradlew check`: six gametests (profile, speed and the two-block step, running a cow
over, coal, the chassis recipe, the radio) and the booth (side stock and red, windshield
and dash from the driver's seat at speed, lamps at night from behind and in front).

## Decisions

D-0001: the cab is repaired in the pipeline as a deterministic edit of the box list, never
at runtime and never by hand-editing the OBJ; every number in the profile is derived from
the same script.

## Next

1.0.0 (2026-09-09). A tuning session with Rusty: top speed, drift, damage, the dial size
and the seat position are numbers to watch, not to plan.
