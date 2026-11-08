#!/bin/bash
# The Unity project's Assets/Editor/*.cs are the SOURCE OF TRUTH (they are what compiles); this repo
# keeps reference copies. They drifted once (the reference copy lacked all of Iceweed's methods), so
# after ANY edit to the Unity copy run this, then commit.
set -e
SRC=/mnt/d/PvZ/ReverseEngineering/AssetBundle-UnityProject/Assets/Editor
DST="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for f in PvZBundleBuilder.cs PvZRipImporter.cs; do
  if ! cmp -s "$SRC/$f" "$DST/$f"; then cp "$SRC/$f" "$DST/$f"; echo "synced $f"; else echo "$f already identical"; fi
done
