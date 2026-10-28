#!/usr/bin/env bash
# Sole full inherited vc13 gauntlet; hasu block A, detached for coordinator watch.
set -eu
lane=/home/mfwolffe/lanes/vc13
repo=$lane/den
head=$1
printf '%s\n' "$$" > "$lane/final.pid"
test ! -e "$lane/final.exit"
printf 'VC13 FINAL START %s pid=%s head=%s\n' "$(date -u +%FT%TZ)" "$$" "$head"
trap 'rc=$?; printf "VC13 FINAL EXIT %s %s\n" "$rc" "$(date -u +%FT%TZ)"; printf "%s\n" "$rc" > "$lane/final.exit"' EXIT
cd "$repo"
test "$(git branch --show-current)" = vc13
test "$(git rev-parse HEAD)" = "$head"
test -z "$(git status --porcelain --untracked-files=no)"
export PATH=/home/mfwolffe/lanes/hasu-env/bin:/home/mfwolffe/lanes/hasu-env/profile/bin:$PATH
flock /home/mfwolffe/lanes/hasu-block-A.lock podman run --rm --memory 12g --pids-limit 16384 --ulimit nproc=32768:32768 --ulimit core=0:0 -e DEN_IN_CONTAINER=1 -e LC_ALL=C -v "$repo:/work/den" -v "$lane/archives:/archives:ro" -w /work/den localhost/den-vc06-oracle:latest taskset -c 0-5 bash -ec '
printf "VC13 FINAL ACQUIRED %s\n" "$(date -u +%FT%TZ)"
python3 -I notes/vc13-evidence/pins/verify.py
python3 -I notes/vc13-evidence/final-inputs.py capture
set +e
tools/gate
rc=$?
printf "VC13 GAUNTLET EXIT %s\n" "$rc"
printf "%s\n" "$rc" > notes/vc13-evidence/gauntlet.exit
set -e
[ "$rc" = 0 ]
python3 -I notes/vc13-evidence/final-inputs.py verify
python3 -I notes/vc13-evidence/final-counts.py notes/vc13-evidence/final-gate.log
' &
job=$!
printf '%s\n' "$job" > "$lane/final-container.pid"
wait "$job"
