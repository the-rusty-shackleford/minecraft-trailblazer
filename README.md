# Trailblazer

A four-door pickup for [Vanilla Wheels](https://github.com/the-rusty-shackleford/minecraft-vanilla-wheels)
on NeoForge 1.21.1. Four seats, the driver's on the left; a double-wide chest in the bed
(six rows); a dash with a speedometer and a fuel gauge you read from the driver's seat;
headlights that light the road; a horn; a radio that plays music discs; a hitch for the
[Trailer](https://github.com/the-rusty-shackleford/minecraft-trailer). It climbs a one-block
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

`devtools/art/preview/trailblazer.bbmodel` is an approved cosmetic derivative of nfx's
Blockbench project. The original is preserved in `devtools/art/reference/`, with its
attribution and checksums. Shaped bonnet, continuous dark arches, recessed rims, restrained cage and bumper chamfers, and coherent metal and rubber shades. The original knobby tyre geometry remains.

Edit the Blockbench source, then run `devtools/art/adopt.py --appearance-only`.
It exports only the body and wheel meshes, supports cube and polygon faces, and refuses
to run if the vehicle profile differs from the frozen released contract. It does not
derive gameplay from the reshaped art or rewrite the profile, recipes or language files.
The importer retains the existing paint correction and selector hierarchy, and centres the wheel on the frozen axle. The modelled chest, driver view, gauges and lamps keep their existing positions.

See D-0005 for the art direction and gameplay boundary. The cosmetic changes in 1.7.0 do not change the driving, interactions or construction described above.

## Verifying it

```
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 PATH="$JAVA_HOME/bin:$PATH"
uv run --no-project python devtools/art/adopt.py --appearance-only
uv run --no-project --with pillow python -m unittest discover -s devtools/art -p "test_appearance.py"
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
`run/booth/` (see Beautiful Wake's booth for the recipe). For server-only checks, run
`./gradlew --no-watch-fs check -PskipBooth`. For the shader booth, use a native GPU display
with Iris, Sodium and Complementary in `run/booth/`. Verify host clients and Xephyr first,
reuse the existing display, and run only one rendering client. The booth mutes itself and exits.

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

The 2026-09-16 held-version comparison keeps the existing driving tune. The rugged
straight and weaving runs had a median 0.891 blocks per tick of movement; all
four Trailblazer runs reached drift release and recorded 40 boost ticks at a maximum
engine speed of 1.158 blocks per tick. There were no stuck reports or server move
rejections. The weave’s eight pauses in yaw change were airborne, with none while
grounded. These are scripted course measurements, not a substitute for subjective
steering or speed preferences.

The playtest now keeps the weave on a wider rugged lane and lets a drift finish beyond
the road boundaries. It fails a missing release/boost or unfinished script, rejects
unknown run names, and logs engine speed separately from distance moved. Run a focused
comparison with `./gradlew runPlaytest -PplaytestRuns=terrain,terrain-weave`; run the
photo booth separately after the client exits. The booth requires its completion
marker and checks shaded paint by hue, with the stock frame as a negative control.
See D-0004 for the reproduced gaps in
the older course. Those driving-harness changes leave all production tuning unchanged; the later cosmetic work is described above.

## Release 1.7.0

The approved cosmetic derivative ships with Vanilla Wheels 1.7.0 and Luminance 1.1.0. Vehicle gameplay data and original supplied-model references are preserved. Update every client and the server together for network protocol 4.

## Licence

AGPL-3.0-or-later. Copyright 2026 Rusty Shackleford and nfx.

## Night and collision playtests

`./gradlew runPlaytest -PplaytestNight
-PplaytestRuns=trailblazer,trailblazer-eyes,terrain-weave` runs the midnight headlight
comparison. The original broad lamp appearance is the reference. The harness mutes
master volume, exits, and records frame mean/p95/p99 in `playtest-performance` lines.
Only one rendering client may run; verify host processes and select the existing display.
Use native GPU rendering for performance claims, with the same shaders and options.

`-PplaytestRuns=impacts` drives the owner's client into a parked truck, glass and stone.
It checks parked-truck displacement, passage through glass and stopping at stone.
The parked target is removed after the contact phase so the later block checks are
independent. `-PplaytestRuns=pickup,pickup-weave -PplaytestPickupJar=/path/to/pickup.jar`
replays the straight and weaving courses with Farmer's Pickup. The optional jar is a
fixture dependency, not shipped content. Each run rejects failure or incomplete scripts.
Fixture-only `run/playtest/options.txt` controls distance trials; personal options do
not belong in distributed packs. A GPU frame-time result on this isolated course does
not establish multiplayer tracking, network cost or server generation capacity.

## Shared materials dependency

Version 1.7.1 bundles Vanilla Wheels 1.7.2, which requires Metals and Materials
as a separately installed mod on both client and server. Mod Hub includes it
in our pack. Vehicle profiles, models, recipes and handling are unchanged.

## Repairs and recovery (1.8.0)

Broken vehicles become packed items at zero condition, preserving cargo, paint,
fuel and radio discs. Wrench pickup also preserves cargo and wear. Place a damaged
vehicle on the Mechanic Lift to reveal Repair; a full repair costs **20 steel
ingots**, with cheaper proportional repairs rounded up. Creative needs no materials.

Use a Vehicle Key Fob on a motor vehicle to pair it. Hold use in air to preview the
fuel bill and recall it together with its currently hitched trailer. The farther
it is, the higher the bill (5% of a full tank at 1,000 blocks; 20% at 2,000).
Missing fuel becomes half as much condition loss. Cargo stays intact even if recall
returns a wreck. Unload passengers and animals, close vehicle chests, and leave room
in inventory. One active pairing per player; a replacement fob invalidates the old.
The fob can recover a paired physical wreck, including from an unloaded chunk, but
cannot duplicate an item someone already collected. A trailer detached by breaking
or wrenching is a separate vehicle.

Requires matching Vanilla Wheels 1.8.0 / protocol 5 on client and server.
Update the full pack on both sides before connecting.
