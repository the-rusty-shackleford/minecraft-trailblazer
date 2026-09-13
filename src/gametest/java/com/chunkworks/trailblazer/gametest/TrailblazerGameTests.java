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

import com.chunkworks.vanillawheels.ModContent;
import com.chunkworks.vanillawheels.Vehicle;
import com.chunkworks.vanillawheels.api.VanillaWheels;
import com.chunkworks.vanillawheels.api.VehicleProfile;
import com.chunkworks.vanillawheels.domain.Impact;
import com.chunkworks.vanillawheels.domain.Input;
import java.util.List;
import java.util.Optional;
import net.minecraft.core.BlockPos;
import net.minecraft.core.NonNullList;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.animal.Cow;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.crafting.CraftingInput;
import net.minecraft.world.item.crafting.CraftingRecipe;
import net.minecraft.world.item.crafting.RecipeHolder;
import net.minecraft.world.item.crafting.RecipeType;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.phys.Vec3;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/**
 * The Trailblazer on a headless server: its profile is registered with four
 * seats, one driver and a chest of six rows; the truck reaches speed on the
 * runway, climbs a one-block step and settles level on top, and a two-block
 * ledge is a wall to it; runs a cow over
 * at speed for the damage its mass and speed say; takes coal into a tank
 * the gauge reads; the chassis crafts from nine steel blocks and names the
 * truck.
 */
@GameTestHolder("trailblazer")
@PrefixGameTestTemplate(false)
public final class TrailblazerGameTests {
    private static final int LENGTH = 48;
    private static final int WIDTH = 15;
    private static final int FLOOR = 4;
    private static final ResourceLocation TRUCK = ResourceLocation.fromNamespaceAndPath("trailblazer", "trailblazer");
    private static final Input GAS = new Input(1, 0, false, true, true);

    public TrailblazerGameTests() {}

    private static void layFloor(GameTestHelper helper) {
        for (int x = 0; x < LENGTH; x++) {
            for (int z = 0; z < WIDTH; z++) {
                for (int y = 0; y < FLOOR; y++) {
                    helper.setBlock(new BlockPos(x, y, z), Blocks.DIRT);
                }
            }
        }
    }

    private static Vehicle truck(GameTestHelper helper, double x, double z) {
        Vehicle v = Vehicle.create(helper.getLevel(), TRUCK, helper.absoluteVec(new Vec3(x, FLOOR, z)), -90.0f);
        helper.assertTrue(v != null, "the Trailblazer is registered");
        v.setFuel(v.tank().capacity());
        helper.getLevel().addFreshEntity(v);
        return v;
    }

    @GameTest(template = "arena", timeoutTicks = 60)
    public void theProfileIsRegisteredWithFourSeatsADriverAChestAndAHitch(GameTestHelper helper) {
        Optional<VehicleProfile> p = VanillaWheels.profile(helper.getLevel().registryAccess(), TRUCK).map(h -> h.value());
        helper.assertTrue(p.isPresent(), "trailblazer:trailblazer is in the vehicle registry");
        VehicleProfile t = p.get();
        helper.assertValueEqual(t.seats().size(), 4, "four seats");
        helper.assertValueEqual((int) t.seats().stream().filter(VehicleProfile.Seat::driver).count(), 1, "one driver");
        helper.assertTrue(t.engine().isPresent(), "an engine");
        helper.assertValueEqual(t.storage().map(VehicleProfile.Storage::rows).orElse(0), 6, "a chest of six rows");
        helper.assertValueEqual(t.wheels().positions().size(), 4, "four wheels");
        helper.assertValueEqual(t.gauges().size(), 2, "two gauges");
        helper.assertTrue(t.hitch().rear().isPresent(), "a hitch");
        helper.assertTrue(t.radio().isPresent(), "a radio");
        helper.assertTrue(t.headlights().isPresent(), "headlights");
        helper.assertTrue(t.handedness() == VehicleProfile.Handedness.RIGHT, "a Blockbench project is in the game's frame");
        Vehicle v = truck(helper, 7.5, 7.5);
        helper.assertTrue(Math.abs(v.getBbWidth() - t.body().width()) < 0.01, "as wide as the profile's tub: " + v.getBbWidth() + " vs " + t.body().width());
        helper.assertTrue(v.getName().getString().equals("Trailblazer"), "named: " + v.getName().getString());
        helper.succeed();
    }

    @GameTest(template = "runway", timeoutTicks = 200)
    public void theTruckReachesSpeedClimbsAOneBlockStepAndAWallOfTwoStopsIt(GameTestHelper helper) {
        layFloor(helper);
        for (int x = 26; x < LENGTH; x++) {
            for (int z = 0; z < WIDTH; z++) {
                helper.setBlock(new BlockPos(x, FLOOR, z), Blocks.STONE);
            }
        }
        Vehicle v = truck(helper, 4.5, 7.5);
        double floorY = helper.absoluteVec(new Vec3(0, FLOOR, 0)).y;
        v.setScriptedInput(GAS);
        helper.runAtTickTime(40, () -> helper.assertTrue(v.speed() > 0.3, "up to speed: " + v.speed()));
        // Brake once it is up, so a truck this long comes to rest on the step with all four wheels on it
        // rather than running off the runway's end.
        helper.runAtTickTime(65, () -> {
            helper.assertTrue(v.getX() > helper.absoluteVec(new Vec3(28, 0, 0)).x, "up the step by now: " + (v.getX() - helper.absoluteVec(new Vec3(0, 0, 0)).x));
            v.setScriptedInput(new Input(-1, 0, false, true, true));
        });
        helper.runAtTickTime(90, () -> v.setScriptedInput(null));
        helper.runAtTickTime(150, () -> {
            helper.assertTrue(v.getX() > helper.absoluteVec(new Vec3(30, 0, 0)).x, "past the step: " + (v.getX() - helper.absoluteVec(new Vec3(0, 0, 0)).x));
            helper.assertTrue(Math.abs(v.getY() - (floorY + 1.0)) < 0.1, "standing one block higher: " + (v.getY() - floorY));
            helper.assertTrue(v.suspension(1.0f).isSettled(), "settled: " + v.suspension(1.0f) + " at " + (v.getX() - helper.absoluteVec(new Vec3(0, 0, 0)).x));
            helper.succeed();
        });
    }

    @GameTest(template = "runway", timeoutTicks = 120)
    public void aTwoBlockLedgeIsAWallToTheTruck(GameTestHelper helper) {
        layFloor(helper);
        for (int x = 20; x < LENGTH; x++) {
            for (int z = 0; z < WIDTH; z++) {
                helper.setBlock(new BlockPos(x, FLOOR, z), Blocks.STONE);
                helper.setBlock(new BlockPos(x, FLOOR + 1, z), Blocks.STONE);
            }
        }
        Vehicle v = truck(helper, 4.5, 7.5);
        double floorY = helper.absoluteVec(new Vec3(0, FLOOR, 0)).y;
        v.setScriptedInput(GAS);
        helper.runAtTickTime(100, () -> {
            helper.assertTrue(Math.abs(v.getY() - floorY) < 0.1, "still on the floor: " + (v.getY() - floorY));
            helper.assertTrue(v.getX() < helper.absoluteVec(new Vec3(20, 0, 0)).x, "held at the wall: " + (v.getX() - helper.absoluteVec(new Vec3(0, 0, 0)).x));
            helper.assertTrue(Math.abs(v.suspension(1.0f).pitch()) < Math.toRadians(5), "level against it, not reared: " + Math.toDegrees(v.suspension(1.0f).pitch()));
            helper.succeed();
        });
    }

    @GameTest(template = "runway", timeoutTicks = 200)
    public void runningACowOverHurtsByTheTrucksMassAndSpeed(GameTestHelper helper) {
        layFloor(helper);
        Vehicle v = truck(helper, 4.5, 7.5);
        Cow cow = EntityType.COW.create(helper.getLevel());
        Vec3 at = helper.absoluteVec(new Vec3(30.5, FLOOR, 7.5));
        cow.setPos(at.x, at.y, at.z);
        cow.setNoAi(true);
        helper.getLevel().addFreshEntity(cow);
        float health = cow.getHealth();
        VehicleProfile p = v.profile();
        double mass = p.mass();
        double max = p.engine().orElseThrow().maxSpeed();
        v.setScriptedInput(GAS);
        helper.runAtTickTime(90, () -> {
            float lost = health - cow.getHealth();
            helper.assertTrue(lost > 0 || cow.isDeadOrDying(), "the cow was hurt: " + cow.getHealth());
            double least = Impact.damage(0.5, max, mass);
            double most = Impact.damage(max, max, mass);
            helper.assertTrue(cow.isDeadOrDying() || (lost >= least && lost <= most + 0.01), "by the truck's mass and speed: lost " + lost + " of " + least + ".." + most);
            helper.succeed();
        });
    }

    @GameTest(template = "arena", timeoutTicks = 60)
    public void coalFillsTheTankTheGaugeReads(GameTestHelper helper) {
        Vehicle v = Vehicle.create(helper.getLevel(), TRUCK, helper.absoluteVec(new Vec3(7.5, 1, 7.5)), 0.0f);
        helper.getLevel().addFreshEntity(v);
        helper.assertValueEqual(v.tank().ticks(), 0, "empty to begin with");
        Player p = helper.makeMockPlayer(GameType.SURVIVAL);
        p.setItemInHand(InteractionHand.MAIN_HAND, new ItemStack(Items.COAL, 3));
        v.interact(p, InteractionHand.MAIN_HAND);
        helper.assertValueEqual(v.tank().ticks(), 1600, "a coal's burn");
        helper.assertTrue(Math.abs(v.fuelFraction() - 1600.0 / 24000.0) < 1e-9, "the gauge reads it: " + v.fuelFraction());
        helper.assertValueEqual(p.getMainHandItem().getCount(), 2, "one coal taken");
        helper.succeed();
    }

    @GameTest(template = "arena", timeoutTicks = 60)
    public void theChassisCraftsFromNineSteelBlocksAndNamesTheTruck(GameTestHelper helper) {
        NonNullList<ItemStack> grid = NonNullList.withSize(9, ItemStack.EMPTY);
        var steelBlock = net.minecraft.core.registries.BuiltInRegistries.ITEM.get(ResourceLocation.fromNamespaceAndPath("metalsandmaterials", "steel_block"));
        helper.assertTrue(steelBlock != Items.AIR, "Metals and Materials' steel block is here");
        for (int i = 0; i < 9; i++) {
            grid.set(i, new ItemStack(steelBlock));
        }
        CraftingInput input = CraftingInput.of(3, 3, grid);
        Optional<RecipeHolder<CraftingRecipe>> recipe = helper.getLevel().getRecipeManager().getRecipeFor(RecipeType.CRAFTING, input, helper.getLevel());
        helper.assertTrue(recipe.isPresent(), "nine steel blocks craft something");
        helper.assertValueEqual(recipe.get().id(), ResourceLocation.fromNamespaceAndPath("trailblazer", "trailblazer_chassis"), "the Trailblazer's chassis recipe");
        ItemStack result = recipe.get().value().assemble(input, helper.getLevel().registryAccess());
        helper.assertTrue(result.is(ModContent.CHASSIS.get()), "a chassis: " + result);
        helper.assertValueEqual(VanillaWheels.vehicleOf(result).orElse(null), TRUCK, "for the Trailblazer");
        helper.assertTrue(result.getHoverName().getString().contains("Trailblazer"), "named for it: " + result.getHoverName().getString());
        helper.succeed();
    }

    @GameTest(template = "arena", timeoutTicks = 60)
    public void aDiscGoesInTheRadioAndComesOut(GameTestHelper helper) {
        Vehicle v = Vehicle.create(helper.getLevel(), TRUCK, helper.absoluteVec(new Vec3(7.5, 1, 7.5)), 0.0f);
        helper.getLevel().addFreshEntity(v);
        Player p = helper.makeMockPlayer(GameType.SURVIVAL);
        p.setShiftKeyDown(true);
        p.setItemInHand(InteractionHand.MAIN_HAND, new ItemStack(Items.MUSIC_DISC_CAT));
        v.interactAt(p, Vec3.ZERO, InteractionHand.MAIN_HAND);
        helper.assertTrue(v.disc().is(Items.MUSIC_DISC_CAT), "the disc is in: " + v.disc());
        helper.assertTrue(p.getMainHandItem().isEmpty(), "and out of the hand");
        p.setItemInHand(InteractionHand.MAIN_HAND, ItemStack.EMPTY);
        VehicleProfile prof = v.profile();
        Vec3 radio = v.rotate(prof.localBlocks(prof.radio().orElseThrow().at()));
        v.interactAt(p, radio, InteractionHand.MAIN_HAND);
        helper.assertTrue(v.disc().isEmpty(), "ejected");
        List<ItemStack> got = p.getInventory().items.stream().filter(s -> s.is(Items.MUSIC_DISC_CAT)).toList();
        helper.assertValueEqual(got.size(), 1, "back in the inventory");
        helper.succeed();
    }
}
