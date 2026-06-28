declare -gA G4PSI_CONFIG=(
  [template]="repo:templates/g4psi/gem_classifier.mac.erb"
  [renderer]="repo:src/freeway/ruby/render_gem_classifier_macro.rb"
  [generated_dir]="repo:macros/generated"
  [gem_classifier_export]="1"
  [gem_classifier_exporter]="repo:src/freeway/python/gem_classifier/export_gem_classifier_table.py"
  [gem_classifier_output]="gem_classifier"
  [gem_classifier_tree]="T"
)
