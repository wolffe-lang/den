#!/usr/bin/env bash
set -eu
lane=/home/mfwolffe/lanes/vc11
repo=$lane/den
printf '%s\n' "$$" > "$lane/final.pid"
printf 'VC11 FINAL START %s pid=%s\n' "$(date -u +%FT%TZ)" "$$"
trap 'rc=$?; printf "VC11 FINAL EXIT %s %s\n" "$rc" "$(date -u +%FT%TZ)"; printf "%s\n" "$rc" > "$lane/final.exit"' EXIT
cd "$repo"
test "$(git branch --show-current)" = vc11
test "$(git rev-parse HEAD)" = 147278f03f5a05a42ea7446e060da6cdc6cbda93
export PATH=/home/mfwolffe/lanes/hasu-env/bin:/home/mfwolffe/lanes/hasu-env/profile/bin:$PATH
flock /home/mfwolffe/lanes/hasu-block-A.lock podman run --rm --memory 12g --ulimit core=0:0 -e DEN_IN_CONTAINER=1 -v "$repo:/work/den" -w /work/den localhost/den-vc06-oracle:latest taskset -c 0-5 bash -ec '
printf "VC11 FINAL ACQUIRED %s\n" "$(date -u +%FT%TZ)"
python3 -I notes/vc11-evidence/pins/verify.py
python3 -I notes/vc11-evidence/final-inputs.py capture
set +e
tools/gate
rc=$?
printf "VC11 GAUNTLET EXIT %s\n" "$rc"
printf "%s\n" "$rc" > notes/vc11-evidence/gauntlet.exit
set -e
[ "$rc" = 0 ]
python3 -I notes/vc11-evidence/final-inputs.py verify
python3 -I notes/vc11-evidence/final-counts.py
' &
job=$!
printf '%s\n' "$job" > "$lane/final-container.pid"
while kill -0 "$job" 2>/dev/null; do
    printf 'VC11 FINAL RUNNING pid=%s %s\n' "$job" "$(date -u +%FT%TZ)"
    python3 -I -c 'import time; time.sleep(60)'
done
wait "$job"
