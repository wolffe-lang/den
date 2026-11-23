# Immutable candidate pin shared by its staging and build checks.
candidate_value() {
    awk -v k="$1" '$1 == k {sub(/^[^=]*= */, ""); gsub(/"/, ""); print; exit}' "$DEN_ROOT/candidate-wolf.toml"
}
