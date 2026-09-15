/*
 * Trailblazer - a vehicle for Vanilla Wheels.
 * Copyright (C) 2026 Rusty Shackleford and nfx
 *
 * This program is free software: you can redistribute it and/or modify it
 * under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or (at your
 * option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License
 * for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program. If not, see <https://www.gnu.org/licenses/>.
 */
package com.chunkworks.trailblazer.gametest;

import com.chunkworks.vanillawheels.Vehicle;
import net.minecraft.client.Camera;
import net.minecraft.client.CameraType;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.minecraft.client.gui.screens.TitleScreen;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.Difficulty;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.animal.Cow;
import net.minecraft.world.level.GameRules;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.LevelSettings;
import net.minecraft.world.level.WorldDataConfiguration;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.levelgen.WorldOptions;
import net.minecraft.world.level.levelgen.presets.WorldPresets;
import net.minecraft.world.phys.Vec3;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.fml.common.EventBusSubscriber;
import net.neoforged.neoforge.client.event.ClientTickEvent;
import net.neoforged.neoforge.client.event.RenderFrameEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Locale;
import java.util.UUID;
import java.util.function.Consumer;

/**
 * A playtest: the same course driven by the Trailblazer, seen from behind
 * and then through the driver's own eyes, and then by an Automobility
 * motorcar, scripted from the driver's client the way a hand would drive,
 * so the two can be compared frame by frame and tick by tick.
 * The course runs east along a lane: a ramp of half steps up two blocks and
 * down again, a ramp up a two-block ledge and a two-block cliff down, a canopy
 * of leaves two blocks over the road, a herd of cows on the road, and an open pad
 * where the script holds a left drift and releases it for the boost. Each
 * tick logs {@code playtest: <who> t=... x= y= z= yaw= v=} (v is the
 * distance moved that tick) and every frame logs {@code playtest-frame: <who> t=... f=...
 * cam=... eye=... dist=...}, the camera against the driver's eye, so a camera that
 * jumps between frames is a number; a run that stops advancing for two seconds is
 * logged as stuck, photographed, and lifted past the obstacle. Frames go to
 * the run's screenshots folder as {@code playtest-<who>-<tag>.png}. The
 * server's own "moved wrongly" lines land in the same log and carry the same
 * timestamps. Client only, active only under {@code trailblazer.playtest};
 * Automobility must be in the run's mods folder.
 */
@EventBusSubscriber(modid = GameTestMod.MOD_ID, value = Dist.CLIENT)
public final class TrailblazerPlaytest {
    private TrailblazerPlaytest() {}

    private static final Logger LOG = LoggerFactory.getLogger("Trailblazer playtest");
    private static final boolean ACTIVE = Boolean.getBoolean("trailblazer.playtest");
    private static final ResourceLocation TRUCK = ResourceLocation.fromNamespaceAndPath("trailblazer", "trailblazer");
    private static final String AUTOMOBILE = "automobility:automobile";
    private static final String AUTOMOBILE_NBT = "{frame:\"automobility:steel_motorcar\",wheels:\"automobility:standard\",engine:\"automobility:iron\"}";

    /** The lane: from x = 0 east, its centre at LANE_Z, HALF blocks either side. */
    private static final int HALF = 4;
    private static final int LANE_Z = 0;
    private static final int LENGTH = 150;
    private static final int START_X = 2;
    /** Where the script begins the drift on the open pad. */
    private static final int PAD_X = 104;
    private static final int STUCK_TICKS = 40;

    private enum Phase { TITLE, LOADING, BUILDING, DRIVING, WATCHING, DONE }

    /** One run: a driver's script over one vehicle. */
    private static final class Run {
        final String who;
        final Consumer<ServerPlayer> spawn;
        final CameraType camera;
        /** The lane's centre z, and whether the script weaves the wheel left and right as it goes. */
        int laneZ = LANE_Z;
        boolean weave = false;
        int tick = 0;
        int drift = -1;        // tick the drift began, -1 before
        int lastShotAt = -1000;
        boolean shotCanopy = false;
        double bestX = Double.NEGATIVE_INFINITY;
        int bestTick = 0;
        double lastX, lastY, lastZ;
        boolean done = false;

        Run(String who, Consumer<ServerPlayer> spawn, CameraType camera) {
            this.who = who;
            this.spawn = spawn;
            this.camera = camera;
        }

        Run onTerrain(boolean weave) {
            this.laneZ = TERRAIN_Z;
            this.weave = weave;
            return this;
        }
    }

    private static boolean muted = false;
    private static Phase phase = Phase.TITLE;
    private static int wait = 0;
    private static Run[] runs;
    private static int current = 0;
    private static UUID vehicle;

    private static int frame = 0;

    /**
     * Every frame of a run: where the camera is, where the driver's eye is, and how far apart, so
     * a frame-to-frame jump of the camera (Rusty: "the screen keeps stuttering as if the camera
     * keeps glitching perspectives") is a number in the log, not an impression.
     */
    @SubscribeEvent
    public static void onFrame(RenderFrameEvent.Post event) {
        if (!ACTIVE || phase != Phase.DRIVING || runs == null || current >= runs.length) {
            return;
        }
        Minecraft mc = Minecraft.getInstance();
        if (mc.player == null || mc.player.getVehicle() == null) {
            return;
        }
        Camera cam = mc.gameRenderer.getMainCamera();
        float partial = event.getPartialTick().getGameTimeDeltaPartialTick(false);
        Vec3 eye = mc.player.getEyePosition(partial);
        Vec3 at = cam.getPosition();
        LOG.info("playtest-frame: {} t={} f={} p={} cam={},{},{} eye={},{},{} dist={} yaw={} pitch={}", runs[current].who, runs[current].tick, frame++, f(partial),
            f(at.x), f(at.y), f(at.z), f(eye.x), f(eye.y), f(eye.z), f(at.distanceTo(eye)), f(cam.getYRot()), f(cam.getXRot()));
    }

    @SubscribeEvent
    public static void onClientTick(ClientTickEvent.Post event) {
        if (!ACTIVE) {
            return;
        }
        Minecraft mc = Minecraft.getInstance();
        if (!muted) {
            // Silent from the first tick, before the title music: Rusty listens to music while these run.
            mc.options.getSoundSourceOptionInstance(net.minecraft.sounds.SoundSource.MASTER).set(0.0);
            muted = true;
        }
        switch (phase) {
            case TITLE -> {
                if (mc.screen instanceof TitleScreen && mc.getOverlay() == null) {
                    phase = Phase.LOADING;
                    createWorld(mc);
                }
            }
            case LOADING -> {
                MinecraftServer server = mc.getSingleplayerServer();
                if (mc.level != null && mc.player != null && mc.screen == null && server != null
                        && mc.level.hasChunkAt(mc.player.blockPosition())) {
                    phase = Phase.BUILDING;
                    mc.options.hideGui = true;
                    mc.options.setCameraType(CameraType.THIRD_PERSON_BACK);
                    // -Dtrailblazer.playtest.runs=terrain,terrain-weave picks runs by name; all of them otherwise.
                    String only = System.getProperty("trailblazer.playtest.runs", "");
                    java.util.List<String> names = only.isEmpty() ? java.util.List.of() : java.util.List.of(only.split(","));
                    runs = java.util.Arrays.stream(new Run[] {
                        new Run("trailblazer", TrailblazerPlaytest::spawnTruck, CameraType.THIRD_PERSON_BACK),
                        new Run("trailblazer-eyes", TrailblazerPlaytest::spawnTruck, CameraType.FIRST_PERSON),
                        new Run("automobility", TrailblazerPlaytest::spawnAutomobile, CameraType.THIRD_PERSON_BACK),
                        new Run("terrain", TrailblazerPlaytest::spawnTruckOnTerrain, CameraType.THIRD_PERSON_BACK).onTerrain(false),
                        new Run("terrain-weave", TrailblazerPlaytest::spawnTruckOnTerrain, CameraType.THIRD_PERSON_BACK).onTerrain(true),
                    }).filter(r -> names.isEmpty() || names.contains(r.who)).toArray(Run[]::new);
                    onServer(mc, TrailblazerPlaytest::build);
                    wait = 100;
                }
            }
            case BUILDING -> {
                if (--wait <= 0) {
                    startRun(mc);
                }
            }
            case DRIVING -> drive(mc);
            case WATCHING -> watch(mc);
            case DONE -> { }
        }
    }

    private static void startRun(Minecraft mc) {
        if (current >= runs.length) {
            startWatch(mc);
            return;
        }
        Run run = runs[current];
        vehicle = null;
        mc.options.setCameraType(run.camera);
        onServer(mc, sp -> {
            run.spawn.accept(sp);
            Entity sv = vehicle == null ? null : sp.serverLevel().getEntity(vehicle);
            if (sv == null) {
                LOG.error("playtest: {} has no vehicle to board", run.who);
                return;
            }
            sp.startRiding(sv, true);
        });
        wait = 0;
        phase = Phase.DRIVING;
        LOG.info("playtest: {} begins", run.who);
    }

    /** The driver's script, one tick. */
    private static void drive(Minecraft mc) {
        Run run = runs[current];
        Entity v = mc.player == null ? null : mc.player.getVehicle();
        if (v == null) {
            if (++wait > 100) {
                LOG.error("playtest: {} never boarded", run.who);
                finishRun(mc);
            }
            return;
        }
        if (run.tick == 0) {
            run.lastX = v.getX();
            run.lastY = v.getY();
            run.lastZ = v.getZ();
            // Third person looks a little down at the vehicle; the driver's own eyes look level over the hood.
            look(mc, run.camera == CameraType.FIRST_PERSON ? 4.0f : 12.0f);
        }
        double moved = Math.sqrt(Math.pow(v.getX() - run.lastX, 2) + Math.pow(v.getY() - run.lastY, 2) + Math.pow(v.getZ() - run.lastZ, 2));
        int steerIn = (mc.options.keyLeft.isDown() ? 1 : 0) - (mc.options.keyRight.isDown() ? 1 : 0);
        String extra = v instanceof Vehicle vw ? " burn=" + f(vw.burn()) + " drifting=" + vw.drifting() + " pitch=" + f(Math.toDegrees(vw.suspension(1.0f).pitch()))
                + " roll=" + f(Math.toDegrees(vw.suspension(1.0f).roll())) + " steerIn=" + steerIn + " steer=" + f(vw.steer()) + " kept=" + f(vw.moveKept()) : "";
        LOG.info("playtest: {} t={} x={} y={} z={} yaw={} v={} ground={}{}", run.who, run.tick, f(v.getX()), f(v.getY()), f(v.getZ()), f(v.getYRot()), f(moved), v.onGround(), extra);
        run.lastX = v.getX();
        run.lastY = v.getY();
        run.lastZ = v.getZ();

        // The keys: gas all the way; on the pad, a left drift for fifty ticks then the release.
        boolean onPad = v.getX() >= PAD_X;
        if (onPad && run.drift < 0) {
            run.drift = run.tick;
            LOG.info("playtest: {} drift begins at t={}", run.who, run.tick);
        }
        int sinceDrift = run.drift < 0 ? -1 : run.tick - run.drift;
        mc.options.keyUp.setDown(true);
        if (run.weave && run.drift < 0 && v.getX() >= 10.0) {
            // The weave: six ticks left, six right, over and over -- a zig-zag about the lane's
            // heading, so every riser is met at an angle and the wheel is always being turned.
            boolean left = (run.tick / 6) % 2 == 0;
            mc.options.keyLeft.setDown(left);
            mc.options.keyRight.setDown(!left);
        } else {
            mc.options.keyLeft.setDown(sinceDrift >= 0 && sinceDrift < 50);
            mc.options.keyRight.setDown(false);
        }
        mc.options.keyJump.setDown(sinceDrift >= 0 && sinceDrift < 50);
        if (sinceDrift == 50) {
            LOG.info("playtest: {} drift released at t={}", run.who, run.tick);
        }

        // One frame under the canopy, where the cage is in the leaves: the camera must not collapse.
        if (!run.shotCanopy && v.getX() >= 75.0) {
            run.shotCanopy = true;
            shoot(mc, "playtest-" + run.who + "-canopy");
        }
        // Frames: every forty ticks on the course, every ten through the drift.
        int every = sinceDrift >= 0 ? 10 : 40;
        if (run.tick - run.lastShotAt >= every) {
            run.lastShotAt = run.tick;
            shoot(mc, "playtest-" + run.who + "-t" + String.format(Locale.ROOT, "%04d", run.tick) + "-x" + (int) v.getX());
        }

        // Stuck: no progress east for two seconds on the course; lift it past whatever stopped it. Not
        // once the drift has begun: the drift curls back west, and a lift there would be a refusal in the log.
        if (!onPad && run.drift < 0) {
            if (v.getX() > run.bestX + 0.25) {
                run.bestX = v.getX();
                run.bestTick = run.tick;
            } else if (run.tick - run.bestTick > STUCK_TICKS) {
                LOG.warn("playtest: {} STUCK at x={} y={} for {} ticks", run.who, f(v.getX()), f(v.getY()), STUCK_TICKS);
                shoot(mc, "playtest-" + run.who + "-stuck-x" + (int) v.getX());
                double toX = Math.floor(v.getX()) + 6;
                onServer(mc, sp -> {
                    Entity sv = sp.serverLevel().getEntity(vehicle);
                    if (sv != null) {
                        int top = run.laneZ == TERRAIN_Z ? sp.serverLevel().getMinBuildHeight() + 3 + rugged((int) toX, run.laneZ) : surface(sp.serverLevel(), (int) toX);
                        sv.teleportTo(toX, top + 1.0, run.laneZ + 0.5);
                    }
                });
                run.bestX = toX;
                run.bestTick = run.tick;
            }
        }

        run.tick++;
        if (sinceDrift >= 90 || run.tick > 1200 || v.getX() > LENGTH - 6 || Math.abs(v.getZ() - (run.laneZ + 0.5)) > HALF_T + 2) {
            finishRun(mc);
        }
    }

    // --- the climb, watched from the side ---------------------------------

    private static final int WATCH_TICKS = 70;
    private static int watched;

    /**
     * effects: stands the player beside the first ramp, looking across it,
     * and sends a truck with a villager aboard up it under the server's own
     * throttle, so the frames show the body's pitch and the rider's lean
     * side-on, which no view from the driver's seat can
     */
    private static void startWatch(Minecraft mc) {
        onServer(mc, sp -> {
            ServerLevel level = sp.serverLevel();
            sp.teleportTo(level, 18.5, surface(level, 18) + 1.0, LANE_Z + 9.5, 180.0f, 8.0f);
            Vehicle v = Vehicle.create(level, TRUCK, new Vec3(9.5, surface(level, 9) + 1.0, LANE_Z + 0.5), -90.0f);
            if (v == null) {
                LOG.error("playtest: no truck for the climb");
                return;
            }
            v.setFuel(v.tank().capacity());
            level.addFreshEntity(v);
            net.minecraft.world.entity.npc.Villager rider = EntityType.VILLAGER.create(level);
            if (rider != null) {
                rider.setPos(9.5, surface(level, 9) + 1.0, LANE_Z + 0.5);
                rider.setNoAi(true);
                level.addFreshEntity(rider);
                rider.startRiding(v, true);
            }
            v.setScriptedInput(new com.chunkworks.vanillawheels.domain.Input(1, 0, false, true, true));
            vehicle = v.getUUID();
        });
        mc.options.setCameraType(CameraType.FIRST_PERSON);
        watched = 0;
        phase = Phase.WATCHING;
        LOG.info("playtest: the climb, watched from the side");
    }

    private static void watch(Minecraft mc) {
        if (mc.player != null) {
            mc.player.setYRot(180.0f);
            mc.player.setXRot(8.0f);
            mc.player.yRotO = 180.0f;
            mc.player.xRotO = 8.0f;
        }
        if (watched >= 10 && watched % 4 == 0) {
            shoot(mc, "playtest-climb-t" + String.format(Locale.ROOT, "%03d", watched));
        }
        if (++watched > WATCH_TICKS) {
            phase = Phase.DONE;
            LOG.info("playtest: done");
            mc.stop();
        }
    }

    private static void finishRun(Minecraft mc) {
        Run run = runs[current];
        mc.options.keyUp.setDown(false);
        mc.options.keyLeft.setDown(false);
        mc.options.keyJump.setDown(false);
        LOG.info("playtest: {} ends at t={}", run.who, run.tick);
        run.done = true;
        onServer(mc, sp -> {
            sp.stopRiding();
            Entity sv = sp.serverLevel().getEntity(vehicle);
            if (sv != null) {
                sv.discard();
            }
            sp.teleportTo(sp.serverLevel(), START_X, surface(sp.serverLevel(), START_X) + 1.0, LANE_Z + 0.5, 270.0f, 10.0f);
        });
        current++;
        phase = Phase.BUILDING;
        wait = 60;
    }

    private static String f(double v) {
        return String.format(Locale.ROOT, "%.3f", v);
    }

    // --- the world -------------------------------------------------------

    private static void createWorld(Minecraft mc) {
        GameRules rules = new GameRules();
        rules.getRule(GameRules.RULE_WEATHER_CYCLE).set(false, null);
        rules.getRule(GameRules.RULE_DAYLIGHT).set(false, null);
        rules.getRule(GameRules.RULE_DOMOBSPAWNING).set(false, null);
        LevelSettings settings = new LevelSettings("Trailblazer playtest", GameType.CREATIVE, false, Difficulty.PEACEFUL,
                true, rules, WorldDataConfiguration.DEFAULT);
        WorldOptions options = new WorldOptions(1L, false, false);
        mc.createWorldOpenFlows().createFreshLevel("trailblazer-playtest", settings, options,
                registries -> registries.registryOrThrow(Registries.WORLD_PRESET).getHolderOrThrow(WorldPresets.FLAT)
                        .value().createWorldDimensions(),
                mc.screen);
    }

    /**
     * The road's height at x in half blocks over the flat world's grass (three over the floor): up a
     * ramp of half steps to two blocks, down a ramp, up a two-block ledge by another ramp, then a
     * two-block drop. Half steps, since an Automobility car climbs a slab and not a block; the truck's
     * block climbing has its own gametest.
     */
    private static int halves(int x) {
        if (x < 16) return 0;
        if (x < 20) return x - 15;          // 1..4 half blocks: a ramp
        if (x < 36) return 4;
        if (x < 40) return 4 - (x - 35);    // down
        if (x < 46) return 0;
        if (x < 50) return x - 45;          // up again
        if (x < 66) return 4;
        return 0;                           // the two-block drop
    }

    /** The rugged lane: its centre z, its half width. */
    private static final int TERRAIN_Z = LANE_Z + 24;
    private static final int HALF_T = 7;

    /**
     * The rugged lane's top solid block at (x, z), over the base: flat to x = 12; a hillside of
     * one-block risers every two blocks whose riser lines run thirty degrees off the lane, four
     * up; a jagged descent, three blocks a riser with a bump on every third column; a field of
     * single raised blocks; a one-block ridge crossing at forty-five degrees, twice; a stair a
     * riser every block, four up and four down; a checkerboard of two-by-two moguls; a flat
     * run-out. What the driver's world is made of, and what the road was not.
     */
    static int rugged(int x, int z) {
        int dz = z - TERRAIN_Z;
        if (x < 12) return 0;
        if (x < 30) return Math.min(4, Math.max(0, (int) Math.floor((x - 12 + dz * 0.6) / 2.0)));
        if (x < 44) return Math.max(0, 4 - (x - 30) / 3) + (Math.floorMod(x + dz, 3) == 0 ? 1 : 0);
        if (x < 60) return Math.floorMod(x * 7 + dz * 13, 5) == 0 ? 1 : 0;
        if (x < 78) {
            int d = x + dz - 60;
            return (d >= 2 && d < 5) || (d >= 10 && d < 13) ? 1 : 0;
        }
        if (x < 82) return x - 77;
        if (x < 86) return 4;
        if (x < 90) return 89 - x;
        if (x < 118) return Math.floorMod(x / 2 + Math.floorDiv(dz, 2), 2);
        return 0;
    }

    /** The y of the road's top solid block at x (a half step leaves a slab on it). */
    private static int surface(ServerLevel level, int x) {
        return level.getMinBuildHeight() + 3 + halves(x) / 2;
    }

    /** effects: lays the course on the server and puts the driver at its start */
    private static void build(ServerPlayer sp) {
        ServerLevel level = sp.serverLevel();
        level.setDayTime(6000L);
        int base = level.getMinBuildHeight() + 3;
        for (int x = -4; x < LENGTH + 4; x++) {
            int top = surface(level, x);
            boolean slab = halves(x) % 2 == 1;
            for (int z = LANE_Z - HALF - 2; z <= LANE_Z + HALF + 2; z++) {
                level.setBlockAndUpdate(new BlockPos(x, base - 1, z), Blocks.STONE.defaultBlockState());
                for (int y = base; y <= top; y++) {
                    level.setBlockAndUpdate(new BlockPos(x, y, z), Blocks.STONE.defaultBlockState());
                }
                for (int y = top + 1; y <= base + 6; y++) {
                    level.setBlockAndUpdate(new BlockPos(x, y, z), Blocks.AIR.defaultBlockState());
                }
                if (slab) {
                    level.setBlockAndUpdate(new BlockPos(x, top + 1, z), Blocks.STONE_SLAB.defaultBlockState());
                }
                // The canopy: leaves two blocks over the road, under the cage top and over the hull.
                if (x >= 70 && x < 80) {
                    level.setBlockAndUpdate(new BlockPos(x, top + 3, z), Blocks.OAK_LEAVES.defaultBlockState().setValue(net.minecraft.world.level.block.LeavesBlock.PERSISTENT, true));
                }
            }
        }
        // The rugged lane beside the road.
        for (int x = -4; x < LENGTH + 4; x++) {
            for (int z = TERRAIN_Z - HALF_T - 2; z <= TERRAIN_Z + HALF_T + 2; z++) {
                int top = base + rugged(x, z);
                level.setBlockAndUpdate(new BlockPos(x, base - 1, z), Blocks.STONE.defaultBlockState());
                for (int y = base; y <= top; y++) {
                    level.setBlockAndUpdate(new BlockPos(x, y, z), Blocks.STONE.defaultBlockState());
                }
                for (int y = top + 1; y <= base + 8; y++) {
                    level.setBlockAndUpdate(new BlockPos(x, y, z), Blocks.AIR.defaultBlockState());
                }
            }
        }
        // The herd, no minds of their own, across the lane.
        int[][] herd = {{86, -3}, {87, 1}, {89, -1}, {90, 3}, {92, 0}, {93, -2}, {95, 2}, {96, -3}};
        for (int[] at : herd) {
            Cow cow = EntityType.COW.create(level);
            if (cow != null) {
                cow.setPos(at[0] + 0.5, base + 1, LANE_Z + at[1] + 0.5);
                cow.setNoAi(true);
                level.addFreshEntity(cow);
            }
        }
        sp.getAbilities().flying = false;
        sp.onUpdateAbilities();
        sp.teleportTo(level, START_X, base + 1.0, LANE_Z + 0.5, 270.0f, 10.0f);
        LOG.info("playtest: course built, the road's top block at y={}", base);
    }

    private static void spawnTruck(ServerPlayer sp) {
        ServerLevel level = sp.serverLevel();
        Vehicle v = Vehicle.create(level, TRUCK, new Vec3(START_X + 2.5, surface(level, START_X) + 1.0, LANE_Z + 0.5), -90.0f);
        if (v == null) {
            LOG.error("playtest: the Trailblazer profile is registered -- Vehicle.create returned null");
            return;
        }
        v.setFuel(v.tank().capacity());
        level.addFreshEntity(v);
        vehicle = v.getUUID();
    }

    private static void spawnTruckOnTerrain(ServerPlayer sp) {
        ServerLevel level = sp.serverLevel();
        int base = level.getMinBuildHeight() + 3;
        Vehicle v = Vehicle.create(level, TRUCK, new Vec3(START_X + 2.5, base + rugged(START_X, TERRAIN_Z) + 1.0, TERRAIN_Z + 0.5), -90.0f);
        if (v == null) {
            LOG.error("playtest: the Trailblazer profile is registered -- Vehicle.create returned null");
            return;
        }
        v.setFuel(v.tank().capacity());
        level.addFreshEntity(v);
        vehicle = v.getUUID();
    }

    private static void spawnAutomobile(ServerPlayer sp) {
        ServerLevel level = sp.serverLevel();
        EntityType<?> type = EntityType.byString(AUTOMOBILE).orElse(null);
        if (type == null) {
            LOG.error("playtest: {} is not registered -- is Automobility in the mods folder?", AUTOMOBILE);
            return;
        }
        Entity e = type.create(level);
        if (e == null) {
            LOG.error("playtest: {} would not create", AUTOMOBILE);
            return;
        }
        net.minecraft.nbt.CompoundTag tag;
        try {
            tag = net.minecraft.nbt.TagParser.parseTag(AUTOMOBILE_NBT);
        } catch (com.mojang.brigadier.exceptions.CommandSyntaxException ex) {
            throw new IllegalStateException(ex);
        }
        net.minecraft.nbt.CompoundTag full = e.saveWithoutId(new net.minecraft.nbt.CompoundTag());
        full.merge(tag);
        e.load(full);
        e.moveTo(START_X + 2.5, surface(level, START_X) + 1.0, LANE_Z + 0.5, -90.0f, 0.0f);
        level.addFreshEntity(e);
        vehicle = e.getUUID();
    }

    // --- the client ------------------------------------------------------

    private static void look(Minecraft mc, float pitch) {
        if (mc.player != null && mc.player.getVehicle() != null) {
            float yaw = mc.player.getVehicle().getYRot();
            mc.player.setYRot(yaw);
            mc.player.setXRot(pitch);
            mc.player.yRotO = yaw;
            mc.player.xRotO = pitch;
        }
    }

    private static void onServer(Minecraft mc, Consumer<ServerPlayer> action) {
        MinecraftServer server = mc.getSingleplayerServer();
        if (server == null || mc.player == null) {
            return;
        }
        UUID id = mc.player.getUUID();
        server.execute(() -> {
            ServerPlayer sp = server.getPlayerList().getPlayer(id);
            if (sp != null) {
                action.accept(sp);
            }
        });
    }

    private static void shoot(Minecraft mc, String name) {
        Screenshot.grab(mc.gameDirectory, name + ".png", mc.getMainRenderTarget(), c -> LOG.info("playtest: {}", c.getString()));
    }
}
