# Promo graphics (Nexus banner, thumbnail)

Scripts that draw the Complete Collection 2 release graphics (Pillow only):

| Script | Output |
|---|---|
| `make_banner.py` | `graphic-cc2-nexus-banner-1300x372-v<VERSION>.png` and the `-plants-only-` overlay version |
| `make_thumbnail.py` | `graphic-cc2-thumbnail-v<VERSION>.png` (1280x720) |
| `spray.py`, `hypno.py`, `logo_ribbon.py` | helpers: the spray-painted "+", hypnotized zombie tiles, the PvZ2 -> Replanted ribbon |

```bash
cd promo
PROMO_VERSION=1.28 PROMO_PLANTS=32 ART_OUT=/some/dir python3 make_banner.py
PROMO_VERSION=1.28 PROMO_PLANTS=32 ART_OUT=/some/dir python3 make_thumbnail.py
```

Per release: set `PROMO_VERSION` / `PROMO_PLANTS`, add the new plants to the `frame(...)` list and the `row` list, and edit the chip texts.

## Inputs that are NOT in this repo (ripped PvZ2 assets)

- Plant frames: `PLANTRIP_A` (default `ReverseEngineering/AssetBundle-UnityProject/Assets/plantrip`, local only) and `PLANTRIP_A2` (default `../unity/Assets/plantrip`, filled by the rip pipeline).
- PvZ2 unpacked data (fonts, logo atlas): `PVZ2_UNPACKED` (default `ReverseEngineering/PvZ2-OBB-Rip/pvz2_original_unpacked/`).
- `promo/assets/` (git-ignored): `zomb/SPR_Almanac_Zombies_<Name>.png` (zombie portraits cut from the PvZ2 almanac atlas) and `two_clean.png` (the "2" of the PvZ2 logo); override the folder with `PROMO_ASSETS`.

Keep ripped assets and the generated images out of git.
