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
- **Fuel**: hold right-click at the truck with Vanilla Wheels' gas can and it pours, a
  full can filling the tank in six seconds; the fuel gauge shows it. A creative driver
  needs none.
- **Pick up**: crouch and right-click with the wrench.

## Driving it

Right-click to board (the driver's seat first); movement keys drive, jump held in a turn
drifts, Left Control honks, H cycles the headlights. Look down from the driver's seat and
the two dials on the dash read your speed and your tank; the needles are real geometry,
turned by the protocol every frame. Right-click the chest in the bed to open it, or press
the inventory key while riding. Crouch and right-click with a music disc to play it; crouch
and right-click the dash empty-handed to eject it. Back the rear hitch onto a trailer's
tongue to tow it.

Numbers: top speed 0.9 blocks a tick (18 m/s), mass 1.45 (a full-speed hit does eleven and
a half), climb 1 block (a two-block ledge is a wall; use a ramp), 32 degrees of steering
lock; four and two thirds blocks long, one and five sixths wide, the cage a little under
three high and the hull -- what the world collides with -- one and three quarters, so it
drives under a two-block canopy with the cage through the leaves. A full drift's boost holds 1.16 blocks a tick for two seconds
with the afterburner out, and in third person the camera stands eight and a half blocks
back.

## How it is made

The truck is a Blockbench project built by hand by nfx -- `devtools/art/preview/trailblazer.bbmodel`,
his V4 of 2026-09-11: the body with its four wheels in place, a chest modelled in the bed
where the game draws its own, and the paint tinted as the game tints it, for looking at in
Blockbench -- to the
reference Rusty gave: an open-top,
roll-caged, light-blue Jeep with a seven-slot grille between slatted lamps, black arch
fenders hugging big treaded tyres, a raked windshield in a silver frame under a flat cage,
a deep nose over a low chamfered bumper, black seats, side mirrors, four doors, a dash
with two dials, a chest in the bed and a hitch. Nothing generates it: change the truck
in Blockbench, then run `devtools/art/adopt.py`, which writes:

- `src/main/resources/assets/trailblazer/vanillawheels/mesh/trailblazer.bbmodel`, the
  body -- everything but the wheels and the modelled chest, its body faces divided by the
  preview's tint so the game's paint multiplies back in -- and
  `trailblazer_wheel.bbmodel`, one wheel moved to the axle's origin: what the game loads,
  as saved.
- `src/main/resources/data/trailblazer/vanillawheels/vehicle/trailblazer.json`, the
  profile, its numbers read off the cubes: the seats off the cushions (four tenths of a
  unit over the cushion's top, nfx's placement, where a player's sitting pose puts the body
  on it), the wheel radius and positions off the wheel folders, the hit boxes off the
  fenders, the collision box as wide as the tub, as long as the body and as tall as the
  hull -- not the cage, windshield or mirrors, which pass through a low canopy -- the
  dials' pivots, the lamps, the chest -- the game's double chest of six rows, drawn where the
  `chest_base` cube stands and scaled to its width -- the hitch off the ball and the radio
  off the dash. The engine, handling, climb, mass and fuel numbers live in the script, for
  tuning; `climb` is one block, since two-block climbs lurched worst.
- the lang file.

The body's paint is the profile's factory colour, the reference's own blue as the shaders
render it, since light-blue dye lifted toward white lands short of it; a dye repaints it as
any vehicle. Selectors in the profile name folders and elements (`body`, `lenses`,
`windshield`, `needle_speed`), never materials. The script refuses nothing silently: a
folder it needs that is missing is an error. The file as received is kept outside the
repo, beside the reference image.

## Verifying it

```
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 PATH="$JAVA_HOME/bin:$PATH"
uv run --no-project python devtools/art/adopt.py     # split the project and write the profile
./gradlew check                                       # gametests and the photo booth (needs a display)
./gradlew runPlaytest                                 # the course, beside an Automobility car (needs a display)
```

Look before you build: open the preview project in Blockbench and turn it, or drive
Blockbench from a script (`--remote-debugging-port` and `Preview.selected.screenshot`)
and look at the renders from the front quarter, the side, the front, the rear quarter
and close up on every joint. Then put the booth's reference shot -- the front-left
quarter at a modeller's 45-degree field of view -- beside the reference image at the
same scale and compare part by part; the shaders change every colour, so measure the
hood's and the cage's against the reference's rather than trusting the swatch. The
windshield that did not meet its frame, the frame that leaned forward, and a whole
truck lit inside out were each plain in a picture and invisible in the numbers.

Eleven gametests on a headless server: the profile is registered as described; the truck
reaches speed and climbs a one-block step, climbs a hillside of one-block risers head on,
at an angle, a riser every block and jagged, and a two-block ledge holds it level; runs a
cow over for the damage its mass and speed say; takes the gas can; crafts its chassis; takes and
ejects a disc. The booth
photographs the truck's side stock and painted red, the view from the driver's seat
straight ahead and down at the dash at speed on half a tank (the needles off their
rests), the three-quarter and rear-quarter views, and the lamps at night from behind
and in front with the beam on the ground; its `booth: PASS/FAIL` lines are the
assertion. Under the pack's shaders: Sodium, Iris and Complementary Unbound in
`run/booth/` (see Beautiful Wake's booth for the recipe). Headless: `Xephyr :7 -screen
1280x720 -ac -br -noreset`, then `DISPLAY=:7 __GLX_VENDOR_LIBRARY_NAME=mesa
LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe MESA_GL_VERSION_OVERRIDE=4.6
MESA_GLSL_VERSION_OVERRIDE=460 ./gradlew check`.

The playtest (`TrailblazerPlaytest`, `./gradlew runPlaytest`) is how the driving is
judged against the mod the pack already has. It lays one course in a flat world -- a ramp
of half steps up two blocks and down, a ramp up a two-block ledge and a cliff off it, a
canopy of leaves two blocks over the road, a herd of cows on the road, and an open pad --
and drives it three times under one script from the driver's client: the truck seen from
behind, the truck through the driver's eyes, and an Automobility steel motorcar; then
drives the truck twice down a rugged lane beside the road -- a hillside of one-block
risers at thirty degrees, a jagged descent, a field of single raised blocks, ridges
crossing at forty-five degrees, a stair a riser every block, a checkerboard of moguls --
once straight and once weaving the wheel six ticks each way, for the stalls and the lost
turns rough ground once gave; then sends a truck with a villager aboard up the first ramp
under the server's own throttle, watched side-on, for the body's pitch and the rider's
lean. `-PplaytestRuns=terrain,terrain-weave` replays only the runs named. Every tick logs
`playtest: <who> t= x= y= z= yaw= v= ground= burn= drifting= pitch= roll= steerIn= steer=
kept=` (kept: the share of the move the world let through) and every frame the camera
against the driver's eye; frames land in
`run/playtest/screenshots/` every forty ticks and every ten through the drift; a run that
stops advancing is logged `STUCK` and lifted on. The server's own `moved wrongly` lines
land in the same log, so `grep -c` of them is the count of moves the server refused. The
Automobility jar is not a dependency: `preparePlaytest` copies it into the run's mods
folder from `-PautomobilityJar=` (default `../tools/playtest/`). Read the numbers first
(the two drifts' yaw a tick, the boost's speed and how long it holds, the refusals), then
the frames.

## Licence

AGPL-3.0-or-later. Copyright 2026 Rusty Shackleford and nfx.
