/*
 * The Trailblazer - a pickup for Vanilla Wheels.
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
import com.chunkworks.vanillawheels.api.VehicleProfile;
import com.mojang.blaze3d.platform.NativeImage;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.function.Consumer;
import java.util.function.IntPredicate;
import java.util.function.Supplier;
import net.minecraft.client.CameraType;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.minecraft.client.gui.screens.TitleScreen;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.Difficulty;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.item.DyeColor;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.GameRules;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.LevelSettings;
import net.minecraft.world.level.WorldDataConfiguration;
import net.minecraft.world.level.levelgen.WorldOptions;
import net.minecraft.world.level.levelgen.presets.WorldPresets;
import net.minecraft.world.phys.Vec3;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.fml.common.EventBusSubscriber;
import net.neoforged.neoforge.client.event.ClientTickEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * The Trailblazer on film: a flat world, the truck a few blocks ahead of
 * the player. Its side in stock light blue and in red; the view from the
 * driver's seat straight ahead (over the hood through the windshield) and
 * down at the dash while the truck is driven at speed on half a tank, the
 * needles off their rests; the lamps at night from behind (the beam on the
 * ground, through Luminance) and from the front (the faces aglow). One
 * {@code booth: PASS} or {@code booth: FAIL} line per check; the Gradle
 * task reads them. Client only, active only under
 * {@code trailblazer.photobooth}.
 */
@EventBusSubscriber(modid = GameTestMod.MOD_ID, value = Dist.CLIENT)
public final class TrailblazerBooth {
    private TrailblazerBooth() {}

    private static final Logger LOG = LoggerFactory.getLogger("Trailblazer booth");
    private static final boolean ACTIVE = Boolean.getBoolean("trailblazer.photobooth");
    private static final ResourceLocation TRUCK = ResourceLocation.fromNamespaceAndPath("trailblazer", "trailblazer");

    private enum Phase { TITLE, LOADING, PLACING, SETTLING, RUNNING, DONE }

    private record Step(int at, Runnable action) {}

    /** Ticks for the world to settle after loading, and between a change and its photo. */
    private static final int HOLD = 100;
    private static final int SETTLE = 60;
    /** Where the player stands; the car sits AHEAD blocks south of it. */
    private static final double X = 0.5;
    private static final double Z = 0.5;
    private static final double AHEAD = 6.5;
    /** The night truck stands further out, nose away, so its beams pool in the sampled rows. */
    private static final double NIGHT_AHEAD = 10.0;

    private static Phase phase = Phase.TITLE;
    private static int tick = 0;
    private static List<Step> steps;
    private static UUID car;
    private static double groundDark = -1.0;

    @SubscribeEvent
    public static void onClientTick(ClientTickEvent.Post event) {
        if (!ACTIVE) {
            return;
        }
        Minecraft mc = Minecraft.getInstance();
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
                    phase = Phase.PLACING;
                    // No HUD: the crosshair, inverted over a dark body, reads as a lit lamp.
                    mc.options.hideGui = true;
                    steps = plan(mc);
                    onServer(mc, TrailblazerBooth::setUp);
                }
            }
            case PLACING -> {
                // The count starts once the client has the player on the mark and the car in view:
                // on a slow renderer the teleport and the spawn land some frames after they are sent.
                if (mc.player != null && mc.player.onGround() && mc.player.distanceToSqr(X, mc.player.getY(), Z) < 0.25 && carId(mc) != -1) {
                    phase = Phase.SETTLING;
                    tick = 0;
                }
            }
            case SETTLING -> {
                // A slow renderer may still be meshing the world around the camera: wait until the
                // truck's paint is actually in the frame, up to twenty seconds.
                if (tick++ % 10 == 0 && (count(mc, TrailblazerBooth::lightBlue) > 200 || tick > 400)) {
                    phase = Phase.RUNNING;
                    tick = 0;
                }
            }
            case RUNNING -> {
                for (Step step : steps) {
                    if (step.at() == tick) {
                        step.action().run();
                    }
                }
                tick++;
            }
            case DONE -> { }
        }
    }

    private static void createWorld(Minecraft mc) {
        GameRules rules = new GameRules();
        rules.getRule(GameRules.RULE_WEATHER_CYCLE).set(false, null);
        rules.getRule(GameRules.RULE_DAYLIGHT).set(false, null);
        rules.getRule(GameRules.RULE_DOMOBSPAWNING).set(false, null);
        LevelSettings settings = new LevelSettings("Trailblazer booth", GameType.CREATIVE, false, Difficulty.PEACEFUL,
                true, rules, WorldDataConfiguration.DEFAULT);
        WorldOptions options = new WorldOptions(1L, false, false);
        mc.createWorldOpenFlows().createFreshLevel("trailblazer-booth", settings, options,
                registries -> registries.registryOrThrow(Registries.WORLD_PRESET).getHolderOrThrow(WorldPresets.FLAT)
                        .value().createWorldDimensions(),
                mc.screen);
    }

    /** Noon; the player on the grass facing south; the truck ahead, side on, facing east, half a tank in. */
    private static void setUp(ServerPlayer sp) {
        ServerLevel level = sp.serverLevel();
        level.setDayTime(6000L);
        sp.getAbilities().flying = false;
        sp.onUpdateAbilities();
        double y = level.getMinBuildHeight() + 5;
        sp.teleportTo(level, X, y, Z, 0.0f, 8.0f);
        sp.setItemInHand(InteractionHand.MAIN_HAND, ItemStack.EMPTY);
        sp.setItemInHand(InteractionHand.OFF_HAND, ItemStack.EMPTY);
        Vehicle v = Vehicle.create(level, TRUCK, new Vec3(X, y, Z + AHEAD), -90.0f);
        if (v == null) {
            LOG.error("booth: FAIL the Trailblazer profile is registered -- Vehicle.create returned null");
            return;
        }
        v.setFuel(v.tank().capacity() / 2);
        level.addFreshEntity(v);
        car = v.getUUID();
    }

    private static List<Step> plan(Minecraft mc) {
        List<Step> s = new ArrayList<>();
        int t = HOLD;
        s.add(new Step(t, () -> {
            int blue = count(mc, TrailblazerBooth::lightBlue);
            int red = count(mc, TrailblazerBooth::red);
            shoot(mc, "booth-side-stock");
            verdict("the stock truck's side shows its light-blue paint", () -> blue > 1500 ? null : "light-blue pixels " + blue);
            verdict("and nothing red", () -> red < 150 ? null : "red pixels " + red);
        }));
        s.add(new Step(t += 2, () -> withCar(mc, v -> v.setPaint(DyeColor.RED))));
        s.add(new Step(t += SETTLE / 2, () -> {
            int blue = count(mc, TrailblazerBooth::lightBlue);
            int red = count(mc, TrailblazerBooth::red);
            shoot(mc, "booth-side-red");
            verdict("painted red, the side is red", () -> red > 1500 ? null : "red pixels " + red);
            verdict("and the blue is gone", () -> blue < 150 ? null : "light-blue pixels " + blue);
        }));
        // Into the driver's seat: straight ahead over the hood, then down at the dash while the server drives.
        s.add(new Step(t += 2, () -> withCar(mc, v -> {
            v.setPaint(DyeColor.LIGHT_BLUE);
            ServerPlayer sp = v.getServer().getPlayerList().getPlayer(mc.player.getUUID());
            if (sp != null) {
                sp.startRiding(v, true);
            }
        })));
        s.add(new Step(t += 10, () -> look(mc, 4.0f)));
        s.add(new Step(t += SETTLE / 2, () -> {
            shoot(mc, "booth-windshield");
            verdict("the driver is aboard", () -> mc.player != null && mc.player.getVehicle() instanceof Vehicle ? null : "vehicle " + (mc.player == null ? null : mc.player.getVehicle()));
            verdict("the driver's eye is under the cage's top", () -> {
                if (!(mc.player != null && mc.player.getVehicle() instanceof Vehicle v)) {
                    return "not aboard";
                }
                double eye = mc.player.getEyeY() - v.getY();
                // The profile's height is the hull's, which the world collides with; the cage stands over it in the mesh.
                double roof = com.chunkworks.vanillawheels.client.MeshLibrary.INSTANCE.get(v.profile().mesh()).bounds().max().y() * v.profile().scale();
                return eye < roof - 0.05 ? null : "eye " + eye + " blocks up, the cage's top " + roof;
            });
        }));
        // The driver's client drives, so the booth holds W the way a hand would.
        s.add(new Step(t += 2, () -> mc.options.keyUp.setDown(true)));
        s.add(new Step(t += 45, () -> lookAtSpeedo(mc)));
        s.add(new Step(t += 6, () -> {
            int needles = countIn(mc, TrailblazerBooth::red, 0.0, 1.0);
            double speed = mc.player != null && mc.player.getVehicle() instanceof Vehicle v ? v.speed() : -1;
            shoot(mc, "booth-dash");
            verdict("at speed on half a tank the dash shows its needles", () -> needles > 40 ? null : "needle pixels " + needles);
            verdict("the truck is moving under the driver", () -> speed > 0.4 ? null : "speed " + speed);
        }));
        // Still driving: the view from behind, as a player in third person sees their own truck, then from the front.
        s.add(new Step(t += 2, () -> {
            look(mc, 12.0f);
            mc.options.setCameraType(CameraType.THIRD_PERSON_BACK);
        }));
        s.add(new Step(t += 15, () -> shoot(mc, "booth-third-person-back")));
        s.add(new Step(t += 2, () -> mc.options.setCameraType(CameraType.THIRD_PERSON_FRONT)));
        s.add(new Step(t += 15, () -> {
            shoot(mc, "booth-third-person-front");
            mc.options.keyUp.setDown(false);
            mc.options.setCameraType(CameraType.FIRST_PERSON);
        }));
        // Out; the driven truck rolls on, so a fresh one stands for the exterior shots: the front-left
        // quarter from above, the reference picture's angle, then the rear quarter for the bed.
        s.add(new Step(t += 2, () -> onServer(mc, sp -> {
            sp.stopRiding();
            ServerLevel level = sp.serverLevel();
            double y = level.getMinBuildHeight() + 5;
            if (level.getEntity(car) instanceof Vehicle old) {
                old.discard();
            }
            Vehicle v = Vehicle.create(level, TRUCK, new Vec3(X, y, Z + AHEAD), -90.0f);
            if (v != null) {
                level.addFreshEntity(v);
                car = v.getUUID();
                sp.getAbilities().flying = true;
                sp.onUpdateAbilities();
                // The reference's own view: front-left quarter, low, at a modeller's narrow field of view.
                sp.teleportTo(level, v.getX() + 8.6, y + 5.6, v.getZ() - 5.1, 59.0f, 25.0f);
            }
        })));
        s.add(new Step(t += 2, () -> mc.options.fov().set(45)));
        s.add(new Step(t += SETTLE / 2, () -> {
            shoot(mc, "booth-three-quarter");
            mc.options.fov().set(70);
        }));
        // Round to the rear quarter for the bed and its chest.
        s.add(new Step(t += 2, () -> onServer(mc, sp -> {
            ServerLevel level = sp.serverLevel();
            double y = level.getMinBuildHeight() + 5;
            if (level.getEntity(car) instanceof Vehicle v) {
                sp.getAbilities().flying = false;
                sp.onUpdateAbilities();
                sp.teleportTo(level, v.getX() - 8.0, y + 3.8, v.getZ() + 7.0, -131.0f, 12.0f);
            }
        })));
        s.add(new Step(t += SETTLE / 2, () -> shoot(mc, "booth-rear-quarter")));
        // Close over the bed from behind, for the chests: the truck faces east, so its bed is to the west of it.
        s.add(new Step(t += 2, () -> onServer(mc, sp -> {
            ServerLevel level = sp.serverLevel();
            double y = level.getMinBuildHeight() + 5;
            if (level.getEntity(car) instanceof Vehicle v) {
                sp.getAbilities().flying = true;   // hangs in the air for the shot
                sp.onUpdateAbilities();
                sp.teleportTo(level, v.getX() - 4.0, y + 4.6, v.getZ() + 0.5, -90.0f, 42.0f);
            }
        })));
        s.add(new Step(t += SETTLE / 2, () -> shoot(mc, "booth-bed")));
        // Up and behind the truck for the night shots.
        s.add(new Step(t += 2, () -> onServer(mc, sp -> {
            ServerLevel level = sp.serverLevel();
            level.setDayTime(18000L);
            double y = level.getMinBuildHeight() + 5;
            if (level.getEntity(car) instanceof Vehicle old) {
                old.discard();
            }
            Vehicle v = Vehicle.create(level, TRUCK, new Vec3(X, y, Z + NIGHT_AHEAD), 0.0f);
            if (v != null) {
                level.addFreshEntity(v);
                car = v.getUUID();
            }
            sp.getAbilities().flying = true;
            sp.onUpdateAbilities();
            sp.teleportTo(level, X, y + 4.5, Z, 0.0f, 32.0f);
        })));
        // Twice the settle: the teleport, the new truck and the night's relit chunks all have to land first, and
        // under llvmpipe one settle has been read before the camera arrived.
        s.add(new Step(t += SETTLE * 2, () -> {
            groundDark = brightness(mc);
            shoot(mc, "booth-night-lamps-off");
            verdict("at night with the lamps off the ground ahead is dark", () -> groundDark < 60 ? null : "brightness " + groundDark);
        }));
        s.add(new Step(t += 2, () -> withCar(mc, Vehicle::cycleLights)));
        s.add(new Step(t += SETTLE + 20, () -> {
            double lit = brightness(mc);
            shoot(mc, "booth-night-lamps-on");
            verdict("the lamps are on", () -> mc.level != null && mc.level.getEntity(carId(mc)) instanceof Vehicle v && v.lit() ? null : "not lit");
            verdict("and the ground ahead is lit through Luminance", () -> lit > groundDark + 15 ? null : "dark " + groundDark + ", lit " + lit);
        }));
        s.add(new Step(t += 2, () -> onServer(mc, sp -> {
            ServerLevel level = sp.serverLevel();
            double y = level.getMinBuildHeight() + 5;
            sp.teleportTo(level, X, y + 0.5, Z + NIGHT_AHEAD + 8.0, 180.0f, 6.0f);
        })));
        s.add(new Step(t += SETTLE, () -> {
            int lamps = count(mc, TrailblazerBooth::lampGlow);
            shoot(mc, "booth-night-lamps-front");
            verdict("with the lamps on the lamp faces glow", () -> lamps > 30 ? null : "glowing lamp pixels " + lamps);
        }));
        s.add(new Step(t += 20, () -> {
            LOG.info("booth: PASS all checks ran");
            phase = Phase.DONE;
            mc.stop();
        }));
        return s;
    }

    /** effects: turns the riding player to face the way the truck does, looking down at the speed gauge's pivot */
    private static void lookAtSpeedo(Minecraft mc) {
        if (mc.player != null && mc.player.getVehicle() instanceof Vehicle v) {
            VehicleProfile.Gauge speedo = v.profile().gauges().stream().filter(g -> g.kind() == VehicleProfile.GaugeKind.SPEED).findFirst().orElseThrow();
            Vec3 pivot = v.position().add(v.rotate(v.profile().localBlocks(speedo.pivot())));
            Vec3 eye = mc.player.getEyePosition();
            double dx = pivot.x - eye.x, dy = pivot.y - eye.y, dz = pivot.z - eye.z;
            look(mc, (float) Math.toDegrees(Math.atan2(-dy, Math.hypot(dx, dz))));
        }
    }

    /** effects: turns the riding player to face the way the truck does, looking {@code pitch} degrees down */
    private static void look(Minecraft mc, float pitch) {
        if (mc.player != null && mc.player.getVehicle() instanceof Vehicle v) {
            mc.player.setYRot(v.getYRot());
            mc.player.setXRot(pitch);
            mc.player.yRotO = v.getYRot();
            mc.player.xRotO = pitch;
        }
    }

    private static int carId(Minecraft mc) {
        if (mc.level == null) {
            return -1;
        }
        for (var e : mc.level.entitiesForRendering()) {
            if (e instanceof Vehicle && e.getUUID().equals(car)) {
                return e.getId();
            }
        }
        return -1;
    }

    // --- reading the frame -----------------------------------------------

    /**
     * The body swatch (grey, noised) under light-blue dye lifted a quarter
     * toward white, about (100, 172, 188) under the shaders, (88, 152, 176)
     * in shade: blue and green well above red, red low -- not the sky, whose
     * red is far higher, and not the grass, whose green leads its blue.
     */
    private static boolean lightBlue(int rgb) {
        int r = rgb >> 16 & 0xFF, g = rgb >> 8 & 0xFF, b = rgb & 0xFF;
        return r < 130 && g > r + 40 && b > r + 60 && b > 140;
    }

    /** The same swatch under red dye, on a lit or a shaded face; not the hazard stripe's yellow. */
    private static boolean red(int rgb) {
        int r = rgb >> 16 & 0xFF, g = rgb >> 8 & 0xFF, b = rgb & 0xFF;
        return r > 80 && g < 110 && r > g + 40 && r > b + 40;
    }

    /** The lens swatch (a warm cream) drawn full bright: far lighter than anything else the night camera sees, shaders included. */
    private static boolean lampGlow(int rgb) {
        int r = rgb >> 16 & 0xFF, g = rgb >> 8 & 0xFF, b = rgb & 0xFF;
        return r > 150 && g > 150 && b > 110;
    }

    /**
     * effects: returns how many pixels of the frame's middle satisfy
     * {@code test} (rgb, no alpha): rows 36..70 % and columns 20..80 %,
     * which is below the sky and above the hotbar and the hand, and where
     * every shot puts the car
     */
    private static int count(Minecraft mc, IntPredicate test) {
        return countIn(mc, test, 0.36, 0.70);
    }

    /** effects: returns how many pixels between the given height fractions, columns 20..80 %, satisfy {@code test} */
    private static int countIn(Minecraft mc, IntPredicate test, double top, double bottom) {
        try (NativeImage image = Screenshot.takeScreenshot(mc.getMainRenderTarget())) {
            int n = 0;
            int w = image.getWidth();
            int h = image.getHeight();
            for (int y = (int) (h * top); y < (int) (h * bottom); y++) {
                for (int x = (int) (w * 0.2); x < (int) (w * 0.8); x++) {
                    int abgr = image.getPixelRGBA(x, y);
                    int rgb = (abgr & 0xFF) << 16 | (abgr >> 8 & 0xFF) << 8 | (abgr >> 16 & 0xFF);
                    if (test.test(rgb)) {
                        n++;
                    }
                }
            }
            return n;
        }
    }

    /**
     * The mean brightness (0..255) of the patch of frame where the beams
     * land: from the night camera (4.5 blocks up, 32 degrees down, the truck
     * 10 blocks ahead facing away) the ground 13..23 blocks out spans about
     * 20..36 % of the frame's height, and the two beams the middle sixth of
     * its width.
     */
    private static double brightness(Minecraft mc) {
        try (NativeImage image = Screenshot.takeScreenshot(mc.getMainRenderTarget())) {
            long sum = 0;
            int n = 0;
            int w = image.getWidth();
            int h = image.getHeight();
            for (int y = (int) (h * 0.2); y < (int) (h * 0.36); y += 2) {
                for (int x = (int) (w * 0.42); x < (int) (w * 0.58); x += 2) {
                    int abgr = image.getPixelRGBA(x, y);
                    sum += (abgr & 0xFF) + ((abgr >> 8) & 0xFF) + ((abgr >> 16) & 0xFF);
                    n += 3;
                }
            }
            return n == 0 ? 0.0 : (double) sum / n;
        }
    }

    // --- plumbing --------------------------------------------------------

    private static void onServer(Minecraft mc, Consumer<ServerPlayer> action) {
        MinecraftServer server = mc.getSingleplayerServer();
        if (server == null || mc.player == null) {
            return;
        }
        server.execute(() -> {
            ServerPlayer sp = server.getPlayerList().getPlayer(mc.player.getUUID());
            if (sp != null) {
                action.accept(sp);
            }
        });
    }

    private static void withCar(Minecraft mc, Consumer<Vehicle> action) {
        onServer(mc, sp -> {
            if (sp.serverLevel().getEntity(car) instanceof Vehicle v) {
                action.accept(v);
            } else {
                LOG.error("booth: FAIL the car is in the level -- gone");
            }
        });
    }

    private static void shoot(Minecraft mc, String name) {
        Screenshot.grab(mc.gameDirectory, name + ".png", mc.getMainRenderTarget(),
                message -> LOG.info("booth: {}", message.getString()));
    }

    /** Runs {@code check}; null is a pass, anything else the failure's detail. */
    private static void verdict(String what, Supplier<String> check) {
        String detail;
        try {
            detail = check.get();
        } catch (RuntimeException e) {
            detail = e.toString();
        }
        if (detail == null) {
            LOG.info("booth: PASS {}", what);
        } else {
            LOG.error("booth: FAIL {} -- {}", what, detail);
        }
    }
}
