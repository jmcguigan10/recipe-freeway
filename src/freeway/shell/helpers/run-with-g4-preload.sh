#!/usr/bin/env bash
set -Eeuo pipefail

work_dir=$1
shift

preload_libs=""

add_preload_lib() {
  local lib="$1"
  [[ -f "$lib" ]] || return 0
  preload_libs="${preload_libs:+$preload_libs:}$lib"
}

for name in libG4processes_core.so libG4particles.so; do
  for lib in "$GEANT4_PREFIX/lib64/$name" "$GEANT4_PREFIX/lib/$name"; do
    if [[ -f "$lib" ]]; then
      add_preload_lib "$lib"
      break
    fi
  done
done

for lib in \
  "${COOKERHOME:-}/muse/lib/libmusetree.so" \
  "${COOKERHOME:-}/muse/lib/libRunInfo.so"; do
  add_preload_lib "$lib"
done

if [[ -n "$preload_libs" ]]; then
  old_preload="${LD_PRELOAD:-}"
  export LD_PRELOAD="$preload_libs${old_preload:+:$old_preload}"
fi

cd "$work_dir"
exec "$@"
