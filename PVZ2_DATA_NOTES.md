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
