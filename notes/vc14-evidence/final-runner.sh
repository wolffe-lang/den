#!/usr/bin/env bash
# Sole full vc14 gauntlet. The orchestrator watches this detached job.
set -euo pipefail
lane=/home/mfwolffe/lanes/vc14
repo=$lane/den
head=$1
printf '%s\n' "$$" > "$lane/final.pid"
test ! -e "$lane/final.exit"
printf 'VC14 FINAL START %s pid=%s head=%s\n' "$(date -u +%FT%TZ)" "$$" "$head"
trap 'rc=$?; printf "VC14 FINAL EXIT %s %s\n" "$rc" "$(date -u +%FT%TZ)"; printf "%s\n" "$rc" > "$lane/final.exit"' EXIT
cd "$repo"
test "$(git branch --show-current)" = vc14
test "$(git rev-parse HEAD)" = "$head"
test -z "$(git status --porcelain --untracked-files=no)"
test ! -e target/housekeeping-native-final
test ! -e target/housekeeping-release-final
export PATH=/home/mfwolffe/lanes/hasu-env/bin:/home/mfwolffe/lanes/hasu-env/profile/bin:$PATH
exec 9>/home/mfwolffe/lanes/hasu-block-B.lock
while ! flock -n 9; do
    printf 'VC14 FINAL WAIT BLOCK B %s\n' "$(date -u +%FT%TZ)"
    python3 -I -c 'import time; time.sleep(60)'
done
printf 'VC14 FINAL ACQUIRED %s\n' "$(date -u +%FT%TZ)"
podman run --rm --memory 12g --pids-limit 16384 --ulimit nproc=32768:32768 --ulimit core=0:0 -e DEN_IN_CONTAINER=1 -e LC_ALL=C -v "$repo:/work/den" -v "$lane/archives:/archives:ro" -w /work/den localhost/den-vc06-oracle:latest taskset -c 6-11 bash -ec '
python3 -I notes/vc14-evidence/pins/verify.py
python3 -I notes/vc14-evidence/final-inputs.py capture
set +e
tools/gate
rc=$?
printf "VC14 GAUNTLET EXIT %s\n" "$rc"
printf "%s\n" "$rc" > notes/vc14-evidence/gauntlet.exit
set -e
python3 -I notes/vc14-evidence/final-inputs.py verify
python3 -I notes/vc14-evidence/collect.py --final
exit "$rc"
'
