#!/usr/bin/env bash
set -eu
lane=/home/mfwolffe/lanes/vc10
repo=$lane/den
printf '%s\n' "$$" > "$lane/final.pid"
printf 'VC10 FINAL START %s pid=%s\n' "$(date -u +%FT%TZ)" "$$"
trap 'rc=$?; printf "VC10 FINAL EXIT %s %s\n" "$rc" "$(date -u +%FT%TZ)"; printf "%s\n" "$rc" > "$lane/final.exit"' EXIT
cd "$repo"
export PATH=/home/mfwolffe/lanes/hasu-env/bin:/home/mfwolffe/lanes/hasu-env/profile/bin:$PATH
flock /home/mfwolffe/lanes/hasu-block-A.lock podman run --rm --memory 12g --ulimit core=0:0 -e DEN_IN_CONTAINER=1 -v "$repo:/work/den" -w /work/den localhost/den-vc06-oracle:latest taskset -c 0-5 bash -ec '
printf "VC10 FINAL ACQUIRED %s\n" "$(date -u +%FT%TZ)"
date -u
python3 -I notes/vc10-evidence/vc10-final-inputs.py capture
set +e
tools/gate
rc=$?
printf "VC10 GAUNTLET EXIT %s\n" "$rc"
printf "%s\n" "$rc" > notes/vc10-evidence/gauntlet.exit
set -e
[ "$rc" = 0 ]
python3 -I notes/vc10-evidence/vc10-final-inputs.py verify
python3 -I notes/vc10-evidence/vc10-final-counts.py
' &
job=$!
printf '%s\n' "$job" > "$lane/final-container.pid"
while kill -0 "$job" 2>/dev/null; do
    printf 'VC10 FINAL RUNNING pid=%s %s\n' "$job" "$(date -u +%FT%TZ)"
    python3 -I -c 'import time; time.sleep(60)'
done
wait "$job"
