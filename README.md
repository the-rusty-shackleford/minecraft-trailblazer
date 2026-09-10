# Trailblazer

A four-door pickup for [Vanilla Wheels](https://github.com/the-rusty-shackleford/minecraft-vanilla-wheels)
on NeoForge 1.21.1. Four seats, the driver's on the left; a double-wide chest in the bed
(six rows); a dash with a speedometer and a fuel gauge you read from the driver's seat;
headlights that light the road; a horn; a radio that plays music discs; a hitch for the
[Trailer](https://github.com/the-rusty-shackleford/minecraft-trailer). It climbs a two-block
ledge, drifts on the jump key, and runs over what it hits. There is no Java in it: the
truck is a vehicle profile, two meshes and a texture, and the protocol does the rest --
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

`devtools/art/build.py` turns the generator's bundle (committed under `devtools/art/src/`)
into what the protocol reads. Measured against the bundle, it repairs what the generator
got wrong for a game with a player in it: the cab was a solid block with a 32 px roof,
and a seated player's eye sits 26 px above the seat, so the driver's head stood above the
roof inside the block. The pipeline hollows the cab into a floor, walls and a bulkhead,
raises the roof, pillars, glass and mirrors 8 px, seats the driver so the eye is 2 px
under the new roof, and puts the seat points in the profile. The gauge cluster sat inside
the hood facing the nose; it is flipped and moved under the windshield facing the driver,
with real needles on the dial centres, and the steering wheel is raised to sit under the
dials. The atlas is regenerated as swatches from the material colours, the paint ones in
grey so a dye colours them, the glass with alpha, and every texture coordinate is pulled
inside its swatch (the generator's polygon caps sit on a corner, which the cutout shader
drops). The bundle is left-handed; the profile says so and the protocol mirrors it once.

## Verifying it

```
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 PATH="$JAVA_HOME/bin:$PATH"
uv run --no-project python devtools/art/build.py     # regenerate the meshes, texture, profile
./gradlew check                                       # gametests and the photo booth (needs a display)
```

Six gametests on a headless server: the profile is registered as described; the truck
reaches speed and climbs a two-block step; runs a cow over for the damage its mass and
speed say; takes coal; crafts its chassis; takes and ejects a disc. The booth photographs
the truck's side stock and painted red, the view from the driver's seat straight ahead
and down at the dash at speed on half a tank (the needles off their rests), and the lamps
at night from behind and in front; its `booth: PASS/FAIL` lines are the assertion.
Headless: `Xephyr :7 -screen 1280x720 -ac -br -noreset`, then `DISPLAY=:7
__GLX_VENDOR_LIBRARY_NAME=mesa LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe ./gradlew check`.

## Licence

AGPL-3.0-or-later. Copyright 2026 Rusty Shackleford and nfx.
