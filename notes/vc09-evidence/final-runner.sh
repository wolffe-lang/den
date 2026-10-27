#!/usr/bin/env bash
set -eu
lane=/home/mfwolffe/lanes/vc09
repo=$lane/den
printf '%s\n' "$$" > "$lane/final.pid"
trap 'rc=$?; date -u; printf "FINAL EXIT %s\n" "$rc"; printf "%s\n" "$rc" > "$lane/final.exit"' EXIT
cd "$repo"
export PATH=/home/mfwolffe/lanes/hasu-env/bin:/home/mfwolffe/lanes/hasu-env/profile/bin:$PATH
date -u
python3 -I notes/vc09-evidence/final-inputs.py capture
flock /home/mfwolffe/lanes/hasu-block-A.lock podman run --rm --memory 12g --ulimit core=0:0 -e DEN_IN_CONTAINER=1 -v "$repo:/work/den" -w /work/den localhost/den-vc06-oracle:latest taskset -c 0-5 bash -ec 'tools/gate; python3 -I notes/vc09-evidence/final-inputs.py verify'
python3 -I notes/vc09-evidence/final-inputs.py verify
