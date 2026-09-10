# Trailblazer

A four-door pickup for [Vanilla Wheels](https://github.com/the-rusty-shackleford/minecraft-vanilla-wheels)
on NeoForge 1.21.1. Four seats, the driver's on the left; a double-wide chest in the bed
(six rows); a dash with a speedometer and a fuel gauge you read from the driver's seat;
headlights that light the road; a horn; a radio that plays music discs; a hitch for the
[Trailer](https://github.com/the-rusty-shackleford/minecraft-trailer). It climbs a two-block
ledge, drifts on the jump key, and runs over what it hits. There is no Java in it: the
truck is a vehicle profile and two Blockbench projects, and the protocol does the rest --
so everything about driving, fuel, storage, lights, towing and the Mechanic Lift is
documented there.

## Getting one

- **Chassis**: nine steel blocks in a crafting grid (81 steel ingots, each three iron and a
  coal through Metals and Materials). The chassis item names the Trailblazer.
- **Build**: put the chassis, four wheels and an engine in a Mechanic Lift and press Build;
  the truck appears on the deck facing the front. Paint it there with a dye.
- **Fuel**: right-click with anything a furnace burns. The tank holds 24 000 burn ticks,
  fifteen coal; the fuel gauge shows it.
- **Pick up**: crouch and right-click with the wrench.

## Driving it

Right-click to board (the driver's seat first); movement keys drive, jump held in a turn
drifts, Left Control honks, H cycles the headlights. Look down from the driver's seat and
the two dials on the dash read your speed and your tank; the needles are real geometry,
turned by the protocol every frame. Crouch and right-click the bed for the chest, or press
the inventory key while riding. Crouch and right-click with a music disc to play it; crouch
and right-click the dash empty-handed to eject it. Back the rear hitch onto a trailer's
tongue to tow it.

Numbers: top speed 0.9 blocks a tick (18 m/s), mass 1.45 (a full-speed hit does eleven and
a half), climb 2 blocks, 32 degrees of steering lock.

## How it is made

The truck is a Blockbench project designed in code, to the reference Rusty gave: an
open-top, roll-caged, light-blue Jeep with a seven-slot grille between slatted lamps,
thick angular black fenders over big treaded tyres, a raked windshield in a silver
frame, a chamfered bumper with fog lamps and a winch, black seats, side mirrors -- given
four doors, a dash with two dials, a chest in the bed and a hitch. `devtools/art/build.py`
writes three projects and the profile:

- `src/main/resources/assets/trailblazer/vanillawheels/mesh/trailblazer.bbmodel`, the
  body, and `trailblazer_wheel.bbmodel`, one wheel: what the game loads, as saved.
- `devtools/art/preview/trailblazer_preview.bbmodel`: the body with its four wheels in
  place and the paint tinted as the light-blue dye tints it in the game, for looking at.
  Open it in Blockbench; it is what a player sees, minus the shaders.
- `src/main/resources/data/trailblazer/vanillawheels/vehicle/trailblazer.json`, the
  profile, whose seat points, dial pivots, lamp positions and wheel slots come from the
  same constants as the cubes.

Every face has its own patch of the one embedded texture, painted by the script: a calm
pixel noise per material, and drawn detail where a face is something (the grille's
slots, the lamps' slats, the bonnet's vents, the door seams, the tail lights, the glass's
glare streak with the pane nearly clear), while the tread, the rims and the dials are
painted by where each texel is in the world, so a turned slab of a tyre gets its share
of the pattern. Body faces are greys the dye multiplies into. Selectors in the profile
name folders and elements (`body`, `lenses`, `windshield`, `needle_speed`), never
materials.

Two conventions bit and are written down in the script: Blockbench's frame is the
game's, +Z the nose, +X the vehicle's left, and a turn about +X by a positive angle
carries the top toward the nose, so the windshield's rake is negative; and a face's
texture rows count from the top, which the protocol flips.

Until someone edits a project by hand in Blockbench, the script is the source and the
files are regenerated from it. The day a hand edit lands, the saved project is the
source: stop running the script for that file, or fold the edit back into it.

## Verifying it

```
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 PATH="$JAVA_HOME/bin:$PATH"
uv run --no-project python devtools/art/build.py     # regenerate the projects and the profile
./gradlew check                                       # gametests and the photo booth (needs a display)
```

Look before you build: open the preview project in Blockbench and turn it, or drive
Blockbench from a script (`--remote-debugging-port` and `Preview.selected.screenshot`)
and look at the renders from the front quarter, the side, the front, the rear quarter
and close up on every joint. The windshield that did not meet its frame and the frame
that leaned forward were both plain in a render and invisible in the numbers.

Six gametests on a headless server: the profile is registered as described; the truck
reaches speed and climbs a two-block step; runs a cow over for the damage its mass and
speed say; takes coal; crafts its chassis; takes and ejects a disc. The booth
photographs the truck's side stock and painted red, the view from the driver's seat
straight ahead and down at the dash at speed on half a tank (the needles off their
rests), the three-quarter and rear-quarter views, and the lamps at night from behind
and in front with the beam on the ground; its `booth: PASS/FAIL` lines are the
assertion. Under the pack's shaders: Sodium, Iris and Complementary Unbound in
`run/booth/` (see Beautiful Wake's booth for the recipe). Headless: `Xephyr :7 -screen
1280x720 -ac -br -noreset`, then `DISPLAY=:7 __GLX_VENDOR_LIBRARY_NAME=mesa
LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe MESA_GL_VERSION_OVERRIDE=4.6
MESA_GLSL_VERSION_OVERRIDE=460 ./gradlew check`.

## Licence

AGPL-3.0-or-later. Copyright 2026 Rusty Shackleford and nfx.
