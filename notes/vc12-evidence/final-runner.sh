#!/usr/bin/env bash
# vc12: the sole full gauntlet at the functional head, hasu block A.
# Launch: setsid -f bash notes/vc12-evidence/final-runner.sh HEAD_SHA \
#         > notes/vc12-evidence/final-gate.log 2>&1 < /dev/null
set -eu
lane=/home/mfwolffe/lanes/vc12
repo=$lane/den
head=$1
printf '%s\n' "$$" > "$lane/final.pid"
rm -f "$lane/final.exit"
printf 'VC12 FINAL START %s pid=%s\n' "$(date -u +%FT%TZ)" "$$"
trap 'rc=$?; printf "VC12 FINAL EXIT %s %s\n" "$rc" "$(date -u +%FT%TZ)"; printf "%s\n" "$rc" > "$lane/final.exit"' EXIT
cd "$repo"
test "$(git branch --show-current)" = vc12
test "$(git rev-parse HEAD)" = "$head"
test -z "$(git status --porcelain --untracked-files=no)"
export PATH=/home/mfwolffe/lanes/hasu-env/bin:/home/mfwolffe/lanes/hasu-env/profile/bin:$PATH
flock /home/mfwolffe/lanes/hasu-block-A.lock podman run --rm --memory 12g \
    --pids-limit 16384 --ulimit nproc=32768:32768 --ulimit core=0:0 \
    -e DEN_IN_CONTAINER=1 -e LC_ALL=C -v "$repo:/work/den" -w /work/den \
    localhost/den-vc06-oracle:latest taskset -c 0-5 bash -ec '
printf "VC12 FINAL ACQUIRED %s\n" "$(date -u +%FT%TZ)"
nproc
python3 -I notes/vc12-evidence/pins/verify.py
python3 -I notes/vc12-evidence/final-inputs.py capture
set +e
tools/gate
rc=$?
printf "VC12 GAUNTLET EXIT %s\n" "$rc"
printf "%s\n" "$rc" > notes/vc12-evidence/gauntlet.exit
set -e
[ "$rc" = 0 ]
python3 -I notes/vc12-evidence/final-inputs.py verify
python3 -I notes/vc12-evidence/retain-components.py
python3 -I notes/vc12-evidence/final-counts.py notes/vc12-evidence/final-gate.log
' &
job=$!
printf '%s\n' "$job" > "$lane/final-container.pid"
while kill -0 "$job" 2>/dev/null; do
    printf 'VC12 FINAL RUNNING pid=%s %s\n' "$job" "$(date -u +%FT%TZ)"
    python3 -I -c 'import time; time.sleep(60)'
done
wait "$job"
