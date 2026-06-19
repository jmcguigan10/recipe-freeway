[[ -n "${MUSE_PIPELINE_G4PSI_FUNC_SH_LOADED:-}" ]] && return 0
MUSE_PIPELINE_G4PSI_FUNC_SH_LOADED=1

prepare_g4psi_config() {
  template="$(resolve_path_spec "${G4PSI_CONFIG[template]:-repo:templates/g4psi/muse.mac.erb}")"
  generated_dir="$(resolve_path_spec "${G4PSI_CONFIG[generated_dir]:-repo:macros/generated}")"
  generated_macro="$generated_dir/$run_tag.mac"
  rootfile="$(stage_output_root g4psi)"

  require_file "$template"
}

render_g4psi_macro() {
  with_dir "$stack_dir" \
    "$stack_dir/scripts/pixi-local" run -e batch \
      ruby "$repo_root/src/ruby/render_macro.rb" \
        --template "$template" \
        --output "$generated_macro" \
        --output-dir "$data_run_dir" \
        --rootfile "$rootfile" \
        --run-tag "$run_tag" \
        --run-nr "$run_nr" \
        --particle "$particle" \
        --particle-tag "$particle_tag" \
        --part "$part" \
        --beam-momentum "$beam_momentum" \
        --n-events "$n_events" \
        --seed-1 "$seed_1" \
        --seed-2 "$seed_2"
}

run_g4psi_macro() {
  with_dir "$stack_dir" \
    "$stack_dir/scripts/pixi-local" run -e batch bash \
      "$stack_dir/scripts/stack-shell.sh" \
      g4PSI "$rad_flag" "$generated_macro"
}

run_g4psi_stage() {
  prepare_g4psi_config

  mkdir -p "$(dirname -- "$generated_macro")"
  mkdir -p "$data_run_dir"

  local rendered_rootfile
  rendered_rootfile="$(render_g4psi_macro)"

  echo "Generated macro: $generated_macro"
  echo "Data run dir:    $data_run_dir"
  echo "Run tag:         $run_tag"
  echo "ROOT output:     $rendered_rootfile"

  run_g4psi_macro
}
