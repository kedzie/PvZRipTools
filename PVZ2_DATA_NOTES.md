# What the PvZ2 data + the Replanted decompile tell you when implementing a ripped plant

Notes for the next session, collected while scoping Dusk Lobber (2026-11-05). Everything under
"Replanted" comes from the Cpp2IL decompile at `ReverseEngineering/Cpp2IL-Decompile` and is
**READ FROM CODE, NOT YET TESTED IN GAME** unless stated.

## Where PvZ2's numbers live (`pvz2_original_unpacked/PACKAGES/`)

* `PLANTTYPES.json` - id, `PlantArchetypes` (`lobber`, `aoe`, `stall`, `shadow`...), world, rarity.
  `python3` one-liner over `objects[].objdata.PlantArchetypes` is how the lobber list below was made.
* `PLANTPROPERTIES.json` - per plant `<Name>Default`: `Cost`, `Hitpoints`, `PacketCooldown`,
  `StartingCooldown`, `Actions[]` (`CooldownTimeMin/Max` seconds between shots, `SpawnOffset`,
  `TriggerType`), `ProjectileLobHeight`, `ProjectileTimeOfFlight`.
* `PROJECTILETYPES.json` - `<Name>Default`: `BaseDamage`, `SplashDamage`, `SplashRadius` (grid
  squares squared, 2.0736 = 1.44 tiles), `DamageFlags` (`lobbed`, `catapult`, `fire`, `ash_death`...),
  `AttachedPAM` / `ImpactPAM`, **`ImpactSoundEvent`** (not in any PAM).
* Sound event -> WEM mapping: see README "Sounds".

## Replanted: how a lob works (`Plant.Fire` -> `Projectile.UpdateLobMotion`)

`Plant.Fire` is a big switch on the plant's `SeedType`; CoreLib's `Plant_Fire_Patch` returns false for
custom seeds, so a custom plant fires from its own `CustomPlantBehaviorController` via
`SpawnProjectile` (= `Board.AddProjectile`). The native lob setup (same maths as PvZ1) is, on the
spawned `Projectile p`, with start `(sx, sy)` = projectile spawn position and target zombie `z`:

```
p.mMotionType = ProjectileMotion.Lobbed          // 1  (enum: Straight0 Lobbed1 Threepeater2 Bee3 ... Homing9)
p.mVelX  = (z.ZombieTargetLeadX(50) - sx - 30) / 120     // always 120 ticks of flight
p.mVelY  = 0                                              // lane stays fixed
p.mVelZ  = (z.GetZombieRect().y - sy) / 120 - 7           // Z is screen-vertical; negative = up
p.mAccZ  = 0.115                                          // gravity
p.mDamageRangeFlags = plant.GetDamageRangeFlags(...)      // else CheckForCollision ignores every zombie
```
No zombie in the lane: target x falls back to 700 (minus start x); the horizontal distance is also
clamped to a per-type maximum. Constants read out of `GameAssembly.dll` (120, 7, 50, 30, 700; gravity
`0x3DEB851F` = 0.115). Field offsets: mPosX 0x7C, mPosY 0x80, mPosZ 0x84, mVelX 0x88, mVelY 0x8C,
mVelZ 0x90, mAccZ 0x94, mMotionType 0xA4, mProjectileType 0xA8, mDamageRangeFlags 0xC0,
mTargetZombieID 0xD4. `CustomProjectileDefinition.m_motionType` is copied onto the projectile in
`ProjectileInitialize`'s postfix, so `Lobbed` can be set there. **Unverified:** the sign of Z in
practice, and roof behaviour (`ProjectileInitialize` calls `Board.StageHasRoof`; lobbed motion looks like it
ignores the slope, which is why vanilla lobbers are the roof plants).

## Replanted: splash damage is hard-coded by projectile TYPE

`Projectile.IsSplashDamage` is true only for `Melon`(3), `Wintermelon`(5), `Fireball`(6) and
`PeashooterFireball`(15). A custom projectile type (id >= 16) gets **no** splash from the engine.
Native rule when it does apply (`DoSplashDamage` / `IsZombieHitBySplash`): primary target takes the
definition's `m_damage`; every OTHER zombie in the same or an adjacent row (|row diff| <= 1) whose rect
overlaps the projectile rect takes `m_damage / 3` (total capped at 7x damage; fireball types differ).
Options for a custom lobber: (A) use the native Melon/Wintermelon type (free splash, but Melon's
look/damage) or (B) custom type and do the splash yourself in `CustomProjectileBehaviorController.
PreDoImpact` - loop `Board.m_zombies`, call the native `Projectile.IsZombieHitBySplash(z)` (works for
any type) and `z.TakeDamage(dmg, flags)`. B keeps PvZ2's own numbers (Dusk Lobber: 30 + 25 splash).

## Lobber shortlist (PvZ2 `lobber` archetype, easiest first)

| Plant | PvZ2 behaviour | Effort |
|---|---|---|
| Dusk Lobber | 30 dmg + 25 splash 3x3, cost 150, recharge 10s, shot every 2.85-3s | low - Melon-like |
| Pepperpult | 50 + 10 splash, fire/ash flags, cost 200, thaws | low-medium |
| Apple Mortar | 30 + splash, homing, 1.75-2s, short stun, cost 250 | medium (stun hook) |
| Akee | bounces 4x, -damage per bounce | high (custom bounce) |
| Sling Pea | 5-shot burst, 25 with PF | high |

## Dusk Lobber specifics found while ripping

* Two art sets in one PAM (normal green + `_dark` blue) - see README pitfalls; `skip_image_suffix`.
* Events: `Play_Plant_DuskLobber_Attack` (frame +1 of `attack`, 3 layers), `use_action` at +11 of
  `attack` (the launch frame = when to spawn the lob; +11 PAM frames), PF events on the unexported
  `plantfood` label, `ImpactSoundEvent` `Play_Plant_DuskLobber_Impact` (3 variants) - wire it in CODE with
  `SetHitSfx` (see README "Sounds" point 4), not as an animation event.
* Projectile art: `T_DUSKLOBBER_PROJECTILE` (3 flight anims, `animation`..`animation3`) and
  `T_DUSKLOBBER_PROJECTILE_HIT` (3 splat anims); both in `IMAGES/768/FULL/EFFECTS`.
* Seed packet UI tile: always R/B-swap (green body, purple thorns).

## Sun plants and instant plants (found while porting Primal Sunflower / Gold Bloom, 2026-11-21)

* **PvZ2 sun amounts**: `Powers.List[].Props` = `SunProducer<N>` and N is the sun per production event
  (POWERS.RTON; `SunProducer125` has a `MinSpread`). PvZ2 Sunflower = SunProducer50 on a 32-36 s cooldown,
  Primal Sunflower = 75 on the same cooldown, Gold Bloom = 125 once (Cost 0, `IsInstant`, `IsConsumable`,
  PacketCooldown 75). Replanted coins: `CoinType.Sun` 25, `SmallSun` 15, `LargeSun` 50.
* **Replanted**: `Plant.Update` -> `UpdateAbilities` dispatches on `mSeedType` with a fixed list; a custom seed
  type never reaches `UpdateProductionPlant`. A custom plant with `PlantSubClass.Shooter` does reach
  `UpdateShooter`, which decrements `mLaunchCounter` every tick regardless of zombies, resets it to
  `mLaunchRate - Rand(15)` at <= 0 and calls `FindTargetAndFire` (a no-op for the custom seed, `Plant.Fire` is
  suppressed). CoreLib reports each reset as `OnLaunchCounterTriggered()`. So a custom sun plant is just
  `Shooter` + `m_launchRate` + `Board.AddCoin(Plant.mX, Plant.mY, CoinType.Sun, CoinMotion.FromPlant)`; no
  CoreLib change needed. Initial counter: native Sunflower/Twin/Marigold use `RandRange(300, rate/2)`, anything
  else `RandRange(0, rate)` (set `Plant.mLaunchCounter` in `PostInitialize` to mimic the sunflower).
* Native Sunflower's launch rate can be read at runtime from `ReloadedUtils.GetPlantDefinition(SeedType.Sunflower).m_launchRate`.
* PAM markers: sun plants put `use_action` on the frame the sun spawns (Primal Sunflower `special` +19),
  Gold Bloom `attack` has three (+20/+29/+38, one burst pulse each). Peapod uses `use_action1..5` (one per
  stacked head; the single-head `attack` has `use_action1`). Peanut: `attack` and `attack2` each have one.

## Instant explosion / chill / stall plants, a nut that explodes, Mega Gatling (2026-11-21; READ FROM CODE, NOT TESTED IN GAME)

PvZ2 data (`PLANTPROPERTIES.json`, all "Actions" are `explode`/`projectile`):

| Plant | Cost | HP | PacketCooldown | What the data says |
|---|---|---|---|---|
| Chilly Pepper | 125 | 300 | 35 | 3 explode Actions: `radius_tiered_row` radius 5.0736 (2.25 tiles) Damage 200 / Splash 100; `row` Freeze 1; `row_adjacent` Chill 1 + Freeze 1 |
| Bombegranate | 150 | 300 | 35 | `radius` 2.0736 (1.44 tiles, "3by3") Damage 1800, Burns; GridItemDamage 200; attack/attack2/attack3 picked per planting. The `seed_*` clips (+ "spawn" archetype) are the Plant Food mini bombs - unused here |
| Explode-o-nut | 50 | 3000 | 10 | Powers: Shield3000 + DamageRadius ExplodeONutDamageLvl1 (numbers not in the JSON). `idle*` = armoured Plant Food look, `damage*` = the normal nut (same as Primal Wall-nut) |
| Stallia | 0 | 300 | 20 | `explode` enemy, StallDuration 12 (Plantfood 18), **Knockback 0**, DieAfterExplode; PAM marks the moment with a `freeze` command, not use_action |
| Mega Gatling | 400 | 300 | 5 | two `PeaDefault` Actions, 1.35-1.5 s each; **GiantPeaDefault (600 dmg) is a SecondaryAction = the Plant Food shot**; `ProjectileLaunchSound` is "" so firing is silent; PAM: one use_action on `attack` +16 |

The explosion/chill/stall VFX of Chilly Pepper, Bombegranate and Stallia are part of their own `attack` clips (frost burst,
crater + smoke, purple cloud), so no native particle is needed for them. Explode-o-nut's PAM has no explosion at all.

Replanted hooks used (all public, signatures from the decompile):
* `Board.KillAllZombiesInRadius(row, x, y, radius, rowRange, burn, DamageRangeFlags)` - Cherry Bomb's blast (115 px, rowRange 1,
  burn = ashes). Bombegranate and Explode-o-nut call it directly.
* `Zombie.ApplyChill(false)` = mChilledCounter max(current, 1000) ticks (10 s, `true` = 20 s, the ice-trap value); read from the ISIL.
  Damage with `DamageFlags.Freeze` calls it too. `Zombie.HitIceTrap()` is the full freeze (random ~4-6 s counter + 20 s chill).
* Stall = `Zombie.ApplyButter()` (public; sets mButteredCounter 400 ticks, skips Zomboni/Boss/unfreezable states) then raise
  `mButteredCounter` to 1200. `Zombie.IsImmobilizied()` = iceTrap>0 || butter>0, so the zombie neither walks nor chews; `UpdateAnimSpeed` freezes
  its animation. Setting only `mIceTrapCounter` would also stop it but skip the ice visuals/ClearIceTrap bookkeeping.
* Native explosion effects: `Board.mApp.AddTodParticle(x, y, Board.MakeRenderOrder(RenderLayer.Top, row, 0), ParticleEffect.Powie)`,
  `Board.ShakeBoard(3, -4)`, `AppCore.GetService<IAudioService>().PlayFoley(FoleyType.Cherrybomb)`.
* "A plant was destroyed" has no CoreLib hook, and none is needed: a Harmony prefix on `Plant.Die` (act only when `mPlantHealth <= 0`, so
  the shovel and end-of-level removals stay quiet) plus one on `Plant.Squish` (Zomboni/Gargantuar flatten without health loss), both in
  the mod (MelonLoader applies `[HarmonyPatch]` classes of any mod assembly), find the controller with `CustomPlantBehaviorController.GetFor`.
* A custom projectile with `ProjectileMotion.Straight` moves at the native pea speed whatever `mVelX` says (UpdateNormalMotion's default
  branch adds a constant per tick); the projectile art is anchored at its BOTTOM (pivot 0.5, 0), so lift `mPosY` by half the sprite height.
