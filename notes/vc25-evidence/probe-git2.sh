#!/usr/bin/env bash
# probe-git2.sh OUT: vc25's second black-box probe of the pinned Git 2.56.0
# (same harness as probe-git.sh): gitlink index stat words, update's fetch
# decision, submodule status's describe annotation, fetch/pull on demand,
# push under submodule.recurse, checkout adding/removing a submodule, rm
# variants, diff/log submodule forms, a symlinked .gitmodules, clone pathspecs.
set -u
OUT=${1:?out}
rm -rf "$OUT"; mkdir -p "$OUT/steps"
export DEN_GIT=/opt/git/bin/git DEN_ENV_ROOT=$OUT/env
ENV="python3 -I /env/environment.py"
W=$OUT/w
mkdir -p "$W"
n=0
run() {
    local name=$1 dir=$2; shift 2
    n=$((n+1)); local f; f=$(printf '%s/steps/%03d-%s' "$OUT" "$n" "$name")
    printf '%q ' "$@" > "$f.argv"; echo >> "$f.argv"; echo "$dir" >> "$f.argv"
    ( cd "$dir" && $ENV "$@" ) > "$f.out" 2> "$f.err" < /dev/null
    echo $? > "$f.rc"
}
g() { run "$@"; }
T=/opt/git/bin/git
A="-c protocol.file.allow=always"
# fixtures: leaf (3 commits, a tag), top with leaf at its first commit
for r in leaf top; do $ENV $T init -q --bare "$W/$r.git"; done
mkdir -p "$W/src" && cd "$W/src"
$ENV $T init -q leaf && cd leaf && echo 1 > f && $ENV $T add f && $ENV $T commit -q -m l1 && \
  $ENV $T tag -a -m 'annotated v1' v1 && echo 2 >> f && $ENV $T commit -q -am l2 && $ENV $T tag light2 && \
  echo 3 >> f && $ENV $T commit -q -am l3 && $ENV $T push -q --tags "$W/leaf.git" main && cd ..
L1=$(cd leaf && $ENV $T rev-parse HEAD~2); L2=$(cd leaf && $ENV $T rev-parse HEAD~1); L3=$(cd leaf && $ENV $T rev-parse HEAD)
$ENV $T init -q top && cd top && $ENV $T remote add origin "$W/top.git" && echo t > t && $ENV $T add t && \
  $ENV $T $A submodule add -q ../leaf.git sub > /dev/null 2>&1 && ( cd sub && $ENV $T -c advice.detachedHead=false checkout -q "$L1" ) && \
  $ENV $T add sub && $ENV $T commit -q -m 'add sub at l1' && $ENV $T push -q origin main && cd ..
TOP="file://$W/top.git"

# ---- 1. gitlink index entries: ls-files --debug and the raw index
$ENV $T $A clone -q --recurse-submodules "$TOP" "$W/c"
C=$W/c
g idx-debug-clone "$C" git ls-files --debug
g idx-stat-sub "$C" stat -c '%d %i %u %g %s %Y %Z %a %F' sub
cp "$C/.git/index" "$OUT/index-after-clone"
( cd "$C/sub" && $ENV $T -c advice.detachedHead=false checkout -q "$L2" )
g idx-add "$C" git add sub
g idx-debug-add "$C" git ls-files --debug
cp "$C/.git/index" "$OUT/index-after-add"
g idx-reset "$C" git reset -q
g idx-debug-reset "$C" git ls-files --debug
g idx-status-after-reset "$C" git status -s
$ENV $T $A clone -q "$TOP" "$W/plain"
g idx-debug-plain "$W/plain" git ls-files --debug
g idx-stat-plain-sub "$W/plain" stat -c '%d %i %u %g %s %Y %Z %a %F' sub
g idx-ls-plain-sub "$W/plain" ls -la sub
cp "$W/plain/.git/index" "$OUT/index-plain-clone"
# ---- 2. submodule status describe annotations
d=$C/sub
for target in "$L1" "$L2" "$L3"; do
  ( cd "$d" && $ENV $T -c advice.detachedHead=false checkout -q "$target" )
  g "desc-at-$(echo $target | cut -c1-7)" "$C" git submodule status
done
( cd "$d" && $ENV $T tag -d v1 > /dev/null && $ENV $T tag -d light2 > /dev/null && $ENV $T -c advice.detachedHead=false checkout -q "$L1" )
g desc-notags-l1 "$C" git submodule status
( cd "$d" && $ENV $T branch -q -D main && $ENV $T update-ref -d refs/remotes/origin/main && $ENV $T update-ref -d refs/remotes/origin/HEAD )
g desc-noref "$C" git submodule status
( cd "$d" && $ENV $T commit -q --allow-empty -m loose )
g desc-noref-new "$C" git submodule status
g desc-cached-noref "$C" git submodule status --cached
# ---- 3. update's fetch decision (rebuild the clone)
rm -rf "$C"; $ENV $T $A clone -q --recurse-submodules "$TOP" "$C"
( cd "$C/sub" && $ENV $T -c advice.detachedHead=false checkout -q "$L3" )
g upd-reachable "$C" git submodule update
g upd-reachable-head "$C/sub" git rev-parse HEAD
( cd "$C/sub" && $ENV $T commit -q --allow-empty -m mine && M=$($ENV $T rev-parse HEAD) && $ENV $T -c advice.detachedHead=false checkout -q "$L1" && \
  cd "$C" && $ENV $T update-index --cacheinfo 160000,$M,sub && echo "$M" > "$OUT/unreachable-sha" )
g upd-unreachable "$C" git submodule update
g upd-unreachable-allowed "$C" git $A submodule update
g upd-unreachable-head "$C/sub" git rev-parse HEAD
( cd "$C" && $ENV $T reset -q --hard && $ENV $T update-index --cacheinfo 160000,2222222222222222222222222222222222222222,sub )
g upd-missing "$C" git $A submodule update
( cd "$C" && $ENV $T reset -q --hard )
echo dirt >> "$C/sub/f"
( cd "$C" && $ENV $T update-index --cacheinfo 160000,$L2,sub )
g upd-dirty-conflict "$C" git submodule update
g upd-dirty-force "$C" git submodule update --force
( cd "$C" && $ENV $T reset -q --hard && $ENV $T submodule update -q )
g upd-uptodate "$C" git submodule update
g upd-init-path "$C" git $A submodule update --init -- sub
g upd-nonsub-path "$C" git submodule update -- t
g upd-unknown-path "$C" git submodule update -- nope
# ---- 4. fetch/pull on demand in the superproject
rm -rf "$C"; $ENV $T $A clone -q --recurse-submodules "$TOP" "$C"
( cd "$W/src/top/sub" && $ENV $T -c advice.detachedHead=false checkout -q "$L2" && cd .. && $ENV $T commit -q -am 'sub to l2' && $ENV $T push -q origin main )
g fetch-default "$C" git fetch
g fetch-default-again "$C" git fetch
g fetch-sub-refs "$C/sub" git for-each-ref
( cd "$W/src/top/sub" && $ENV $T -c advice.detachedHead=false checkout -q "$L3" && cd .. && $ENV $T commit -q -am 'sub to l3' && $ENV $T push -q origin main )
g fetch-allowed "$C" git $A fetch
g fetch-no-recurse "$C" git fetch --no-recurse-submodules
g pull-default "$C" git $A pull --no-rebase
g pull-status "$C" git status
g pull-sm "$C" git submodule status
( cd "$C" && $ENV $T reset -q --hard HEAD~2 )
g pull-recurse "$C" git $A pull --no-rebase --recurse-submodules
g pull-recurse-sm "$C" git submodule status
( cd "$C" && $ENV $T reset -q --hard HEAD~2 )
g pull-recurse-cfg "$C" git $A -c submodule.recurse=true pull --no-rebase
g pull-recurse-cfg-sm "$C" git submodule status
# ---- 5. push with an unpushed submodule commit
( cd "$C/sub" && $ENV $T commit -q --allow-empty -m 'local only' && cd .. && $ENV $T add sub && $ENV $T commit -q -m 'sub local' )
g push-default "$C" git push -q origin HEAD:refs/heads/p1
g push-recurse-cfg "$C" git -c submodule.recurse=true push origin HEAD:refs/heads/p2
g push-recurse-check "$C" git push --recurse-submodules=check origin HEAD:refs/heads/p3
g push-recurse-cfg-explicit-no "$C" git -c submodule.recurse=true push --recurse-submodules=no origin HEAD:refs/heads/p4
# ---- 6. checkout adding/removing a submodule; switch
rm -rf "$W/src/top2"; ( cd "$W/src" && $ENV $T clone -q "$TOP" top2 && cd top2 && $ENV $T rm -q sub && $ENV $T commit -q -m 'remove sub' && $ENV $T push -q origin HEAD:refs/heads/nosub )
rm -rf "$C"; $ENV $T $A clone -q --recurse-submodules "$TOP" "$C"
g co-remove "$C" git checkout nosub
g co-remove-status "$C" git status
g co-remove-ls "$C" ls -a sub
g co-add "$C" git checkout main
g co-add-status "$C" git status
g co-add-sm "$C" git submodule status
rm -rf "$W/p2"; $ENV $T clone -q "$TOP" "$W/p2"
g co-plain-remove "$W/p2" git checkout nosub
g co-plain-remove-ls "$W/p2" ls -a
g co-plain-add "$W/p2" git checkout main
g co-plain-add-ls "$W/p2" ls -a sub
g co-recurse-remove "$C" git checkout --recurse-submodules nosub
g co-recurse-remove-ls "$C" ls -a
g co-recurse-add "$C" git $A checkout --recurse-submodules main
g co-recurse-add-sm "$C" git submodule status
# ---- 7. rm variants
rm -rf "$C"; $ENV $T $A clone -q --recurse-submodules "$TOP" "$C"
g rm-cached "$C" git rm --cached sub
g rm-cached-status "$C" git status -s
g rm-cached-ls "$C" ls -a sub
( cd "$C" && $ENV $T reset -q --hard )
echo dirt >> "$C/sub/f"
g rm-dirty "$C" git rm sub
g rm-dirty-force "$C" git rm -f sub
g rm-dirty-force-status "$C" git status -s
g rm-dirty-force-modules "$C" ls .git/modules
( cd "$C" && $ENV $T reset -q --hard )
g rm-restored-ls "$C" ls -a sub
g rm-r-dir "$C" git rm -r -n .
# ---- 8. diff/log forms: added, deleted, typechange, rewind, commits not present
rm -rf "$C"; $ENV $T $A clone -q --recurse-submodules "$TOP" "$C"
( cd "$C" && $ENV $T rm -q sub && $ENV $T commit -q -m del )
g diff-deleted "$C" git diff HEAD~1 HEAD
g diff-deleted-log "$C" git diff --submodule=log HEAD~1 HEAD
g diff-added "$C" git diff HEAD HEAD~1
g diff-added-log "$C" git diff --submodule=log HEAD HEAD~1
g diff-added-stat "$C" git diff --stat HEAD HEAD~1
g diff-added-summary "$C" git diff --summary HEAD HEAD~1
( cd "$C" && $ENV $T reset -q --hard HEAD~1 && $ENV $T submodule update -q )
( cd "$C/sub" && $ENV $T -c advice.detachedHead=false checkout -q "$L3" && cd .. && $ENV $T commit -q -am up )
g diff-rewind-log "$C" git diff --submodule=log HEAD HEAD~1
g diff-forward-log "$C" git diff --submodule=log HEAD~1 HEAD
g log-p-log "$C" git log -p --submodule=log -1
g diff-cfg-log "$C" git -c diff.submodule=log diff HEAD~1 HEAD
g diff-cfg-diff "$C" git -c diff.submodule=diff diff HEAD~1 HEAD
g diff-cfg-log-override "$C" git -c diff.submodule=log diff --submodule=short HEAD~1 HEAD
( cd "$C" && $ENV $T update-index --cacheinfo 160000,3333333333333333333333333333333333333333,sub )
g diff-notpresent-log "$C" git diff --cached --submodule=log
g diff-notpresent "$C" git diff --cached
( cd "$C" && $ENV $T reset -q --hard )
# a gitlink becoming a file and back: typechange
( cd "$C" && $ENV $T rm -q --cached sub && rm -rf sub && echo file > sub && $ENV $T add sub && $ENV $T commit -q -m typechange )
g diff-typechange "$C" git diff HEAD~1 HEAD
g diff-typechange-log "$C" git diff --submodule=log HEAD~1 HEAD
g diff-typechange-raw "$C" git diff --raw HEAD~1 HEAD
g diff-typechange-ns "$C" git diff --name-status HEAD~1 HEAD
( cd "$C" && $ENV $T reset -q --hard HEAD~1 )
# a submodule not checked out (deinitialized form): status/diff
rm -rf "$W/p3"; $ENV $T clone -q "$TOP" "$W/p3"
g uninit-status "$W/p3" git status
g uninit-diff "$W/p3" git diff
( cd "$W/p3" && $ENV $T update-index --cacheinfo 160000,$L2,sub )
g uninit-moved-status "$W/p3" git status
g uninit-moved-diff "$W/p3" git diff --cached
g uninit-moved-diff-log "$W/p3" git diff --cached --submodule=log
rmdir "$W/p3/sub"
g uninit-missing-dir-status "$W/p3" git status -s
# ---- 9. ignore settings from .gitmodules and config
rm -rf "$C"; $ENV $T $A clone -q --recurse-submodules "$TOP" "$C"
echo u > "$C/sub/u"; echo m >> "$C/sub/f"
for ig in none untracked dirty all; do
  g "ign-$ig-status" "$C" git -c submodule.sub.ignore=$ig status -s
  g "ign-$ig-diff" "$C" git -c submodule.sub.ignore=$ig diff
done
( cd "$C" && $ENV $T config -f .gitmodules submodule.sub.ignore untracked )
g ign-gitmodules-status "$C" git status -s
g ign-gitmodules-cli "$C" git status -s --ignore-submodules=none
g ign-status-long "$C" git status
( cd "$C" && $ENV $T checkout -q .gitmodules )
g status-summary "$C" git -c status.submoduleSummary=true status
# ---- 10. a symlinked .gitmodules, clone with a pathspec, foreach $path
rm -rf "$W/sym" "$W/sym.git"; $ENV $T init -q --bare "$W/sym.git"
( cd "$W/src" && rm -rf sym && $ENV $T init -q sym && cd sym && echo x > real && ln -s real .gitmodules && $ENV $T add real .gitmodules && $ENV $T commit -q -m sym ) > "$OUT/sym-build" 2>&1
g sym-commit-log "$W/src/sym" git log --oneline
( cd "$W/src/sym" && $ENV $T push -q "$W/sym.git" main ) >> "$OUT/sym-build" 2>&1
g sym-push-rc "$W/src/sym" git push "$W/sym.git" main
g sym-clone "$W" git clone "file://$W/sym.git" c-sym
g clone-pathspec "$W" git $A clone --recurse-submodules=sub "$TOP" c-ps
g clone-pathspec-config "$W/c-ps" git config --get-all submodule.active
g clone-pathspec-none "$W" git $A clone --recurse-submodules=nomatch "$TOP" c-ps2
g clone-pathspec-none-sm "$W/c-ps2" git submodule status
g foreach-path "$C" git submodule foreach 'echo "$path"'
g foreach-cmd-args "$C" git submodule foreach echo a b
g sm-status-paths "$C" git submodule status sub t
g sm-init-twice "$C" git submodule init
g sm-sync-unregistered "$W/p3" git submodule sync
g sm-unknown-sub "$C" git submodule frobnicate
g sm-add-unsupported-den-surface "$C" git submodule summary
echo "PROBE2 DONE $n steps"
