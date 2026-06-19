#!/usr/bin/env bash
set -Eeuo pipefail

work_dir=$1
shift

g4_preload=""

for name in libG4processes_core.so libG4particles.so; do
  for lib in "$GEANT4_PREFIX/lib64/$name" "$GEANT4_PREFIX/lib/$name"; do
    if [[ -f "$lib" ]]; then
      g4_preload="${g4_preload:+$g4_preload:}$lib"
      break
    fi
  done
done

if [[ -n "$g4_preload" ]]; then
  old_preload="${LD_PRELOAD:-}"
  export LD_PRELOAD="$g4_preload${old_preload:+:$old_preload}"
fi

cd "$work_dir"
exec "$@"