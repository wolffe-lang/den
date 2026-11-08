#!/usr/bin/env bash
# probe-git.sh OUT: black-box runs of the pinned Git 2.56.0 for vc25's
# prediction (submodules). Runs inside the den oracle image with the oracle at
# /opt/git, under den's pinned environment (tools/environment.py from den
# 474a926, mounted at /env). Every step records argv, exit status, stdout and
# stderr under OUT/steps/NNN-name.{argv,out,err,rc}; dumps record on-disk state.
# No network: every URL is a local path, file://, or resolved only (init).
set -u
OUT=${1:?out}
rm -rf "$OUT"; mkdir -p "$OUT/steps"
export DEN_GIT=/opt/git/bin/git DEN_ENV_ROOT=$OUT/env
ENV="python3 -I /env/environment.py"
W=$OUT/w
mkdir -p "$W"
n=0
run() { # run NAME DIR CMD... (CMD run under the pinned environment, in DIR)
    local name=$1 dir=$2; shift 2
    n=$((n+1)); local f; f=$(printf '%s/steps/%03d-%s' "$OUT" "$n" "$name")
    printf '%q ' "$@" > "$f.argv"; echo >> "$f.argv"; echo "$dir" >> "$f.argv"
    ( cd "$dir" && $ENV "$@" ) > "$f.out" 2> "$f.err" < /dev/null
    echo $? > "$f.rc"
}
dump() { # dump NAME DIR: every file under DIR except objects, with contents for text files
    local name=$1 dir=$2
    n=$((n+1)); local f; f=$(printf '%s/steps/%03d-dump-%s' "$OUT" "$n" "$name")
    ( cd "$dir" && find . \( -path '*/objects/*' -o -path './objects' \) -prune -o -print | LC_ALL=C sort > "$f.tree"
      find . \( -path '*/objects/*' -o -name index -o -path '*/objects' \) -prune -o -type f -print | LC_ALL=C sort | while read -r p; do
        case "$p" in *.pack|*.idx|*.rev) continue;; esac
        printf '=== %s (mode %s)\n' "$p" "$(stat -c %a "$p")"; cat "$p"; echo; done > "$f.files" )
}
g() { run "$@"; }
T=/opt/git/bin/git

# ---- fixtures: leaf <- mid (relative ../leaf.git, name leafsub at deps/leaf) <- top
mkdir -p "$W/src"
cd "$W/src"
for r in leaf mid top; do $ENV $T init -q --bare "$W/$r.git"; done
$ENV $T init -q leaf && cd leaf && echo one > leaf.txt && $ENV $T add leaf.txt && $ENV $T commit -q -m 'leaf one' && \
  echo two >> leaf.txt && $ENV $T commit -q -am 'leaf two' && $ENV $T push -q "$W/leaf.git" main && cd ..
$ENV $T init -q mid && cd mid && $ENV $T remote add origin "$W/mid.git" && echo mid > mid.txt && $ENV $T add mid.txt && \
  $ENV $T -c protocol.file.allow=always submodule add -q --name leafsub ../leaf.git deps/leaf > /dev/null 2>&1; \
  $ENV $T commit -q -m 'mid with leaf' ; $ENV $T push -q origin main; cd ..
# a relative URL needs the superproject's remote at add time: record what add wrote
cp "$W/src/mid/.gitmodules" "$OUT/mid.gitmodules" 2>/dev/null
$ENV $T init -q top && cd top && $ENV $T remote add origin "$W/top.git" && echo top > top.txt && $ENV $T add top.txt && \
  $ENV $T -c protocol.file.allow=always submodule add -q --name midname ../mid.git mid > /dev/null 2>&1; \
  $ENV $T -c protocol.file.allow=always submodule add -q -b main "file://$W/leaf.git" abs > /dev/null 2>&1; \
  $ENV $T commit -q -m 'top with mid and abs'; $ENV $T push -q origin main; cd ..
cp "$W/src/top/.gitmodules" "$OUT/top.gitmodules"
TOP="file://$W/top.git"

# ---- 1. protocol.file.allow default: recursive clone refuses file submodules
g clone-recurse-default "$W" git clone --recurse-submodules "$TOP" c-default
dump clone-recurse-default "$W/c-default"
# ---- 2. recursive clone, file allowed
g clone-recurse "$W" git -c protocol.file.allow=always clone --recurse-submodules "$TOP" c
dump clone-recurse "$W/c"
g clone-recurse-q "$W" git -c protocol.file.allow=always clone -q --recurse-submodules "$TOP" cq
C=$W/c
g sub-head-mid "$C/mid" git rev-parse HEAD
g sub-symref-mid "$C/mid" git symbolic-ref -q HEAD
g sub-branch-mid "$C/mid" git branch -a
g sub-status-mid "$C/mid" git status
g sub-revparse-gitdir "$C/mid/deps/leaf" git rev-parse --git-dir --show-toplevel --show-superproject-working-tree
# ---- 3. plain clone, then init / update
g clone-plain "$W" git clone "$TOP" p
dump clone-plain "$W/p"
g plain-status "$W/p" git status
g plain-status-porcelain "$W/p" git status --porcelain
g plain-sm-status "$W/p" git submodule status
g plain-sm-bare "$W/p" git submodule
g plain-sm-init "$W/p" git submodule init
dump plain-after-init "$W/p/.git"
g plain-sm-status-init "$W/p" git submodule status
g plain-sm-update "$W/p" git -c protocol.file.allow=always submodule update
g plain-sm-status-upd "$W/p" git submodule status --recursive
g plain-sm-update-init-rec "$W/p" git -c protocol.file.allow=always submodule update --init --recursive
g plain-sm-status-rec "$W/p" git submodule status --recursive
g plain-sm-update-again "$W/p" git -c protocol.file.allow=always submodule update --init --recursive
dump plain-after-update "$W/p"
# ---- 4. status and diff forms in the recursive clone
g st-clean "$C" git status
g st-clean-s "$C" git status -s
g st-clean-porc "$C" git status --porcelain
# untracked content in a submodule
echo u > "$C/mid/untracked.txt"
g st-untracked "$C" git status
g st-untracked-s "$C" git status -s
g st-untracked-porc "$C" git status --porcelain
g diff-untracked "$C" git diff
g diff-untracked-short "$C" git diff --submodule=short
g diff-untracked-log "$C" git diff --submodule=log
g diff-untracked-diff "$C" git diff --submodule=diff
g st-untracked-ign-untracked "$C" git status --ignore-submodules=untracked
# modified content
echo changed >> "$C/mid/mid.txt"
g st-modified "$C" git status
g st-modified-s "$C" git status -s
g st-modified-porc "$C" git status --porcelain
g diff-modified "$C" git diff
g diff-modified-log "$C" git diff --submodule=log
g diff-modified-diff "$C" git diff --submodule=diff
g diff-modified-stat "$C" git diff --stat
# new commits (and dirty)
( cd "$C/mid" && $ENV $T commit -q -am 'mid two' )
g st-newcommits-dirty "$C" git status
g st-newcommits-dirty-s "$C" git status -s
g st-newcommits-dirty-porc "$C" git status --porcelain
g st-newcommits-dirty-porc-z "$C" git status --porcelain -z
g diff-newcommits-dirty "$C" git diff
g diff-newcommits-dirty-log "$C" git diff --submodule=log
g diff-newcommits-dirty-diff "$C" git diff --submodule=diff
g diff-newcommits-dirty-ignore-dirty "$C" git diff --ignore-submodules=dirty
rm "$C/mid/untracked.txt"
g st-newcommits "$C" git status
g st-newcommits-s "$C" git status -s
g diff-newcommits "$C" git diff
g diff-newcommits-log "$C" git diff --submodule=log
g diff-newcommits-diff "$C" git diff --submodule=diff
g diff-newcommits-stat "$C" git diff --stat
g diff-newcommits-numstat "$C" git diff --numstat
g diff-newcommits-name-status "$C" git diff --name-status
g diff-newcommits-raw "$C" git diff --raw
# nested: untracked deep inside
echo deep > "$C/mid/deps/leaf/deep.txt"
g st-nested-untracked "$C" git status
g st-nested-untracked-s "$C" git status -s
g st-nested-untracked-porc "$C" git status --porcelain
rm "$C/mid/deps/leaf/deep.txt"
# stage the moved gitlink, commit, read it back
g add-moved "$C" git add mid
g st-staged "$C" git status
g st-staged-s "$C" git status -s
g diff-cached "$C" git diff --cached
g diff-cached-log "$C" git diff --cached --submodule=log
g commit-moved "$C" git commit -m 'move mid'
g log-p "$C" git log -p -1
g log-stat "$C" git log --stat -1
g show "$C" git show
g show-log "$C" git show --submodule=log
g show-diff "$C" git show --submodule=diff
g ls-tree "$C" git ls-tree HEAD
g ls-tree-r "$C" git ls-tree -r HEAD
g ls-tree-path "$C" git ls-tree HEAD mid
g ls-files-s "$C" git ls-files -s
g ls-files "$C" git ls-files
g catfile-tree "$C" git cat-file -p 'HEAD^{tree}'
g catfile-gitlink-t "$C" sh -c 'git cat-file -t $(git rev-parse HEAD:mid)'
g catfile-gitlink-p "$C" sh -c 'git cat-file -p $(git rev-parse HEAD:mid)'
g revparse-gitlink "$C" git rev-parse HEAD:mid
g show-gitlink "$C" git show HEAD:mid
g diff-two-commits "$C" git diff HEAD~1 HEAD
g diff-two-commits-log "$C" git diff --submodule=log HEAD~1 HEAD
# commit -a with a moved gitlink
( cd "$C/mid" && echo three >> mid.txt && $ENV $T commit -q -am 'mid three' )
g commit-a "$C" git commit -a -m 'move mid again'
g log-oneline "$C" git log --oneline
# ---- 5. submodule status/foreach/sync
g sm-status "$C" git submodule status
g sm-status-rec "$C" git submodule status --recursive
g sm-status-cached "$C" git submodule status --cached
( cd "$C/mid" && $ENV $T -c advice.detachedHead=false checkout -q HEAD~1 )
g sm-status-plus "$C" git submodule status
g sm-foreach "$C" git submodule foreach 'echo "$name|$sm_path|$displaypath|$sha1|$toplevel"'
g sm-foreach-rec "$C" git submodule foreach --recursive 'echo "$name|$sm_path|$displaypath|$sha1|$toplevel"'
g sm-foreach-q "$C" git submodule --quiet foreach 'echo $name'
g sm-foreach-fail "$C" git submodule foreach 'exit 3'
g sm-foreach-sub "$C/mid" git submodule foreach 'echo in $displaypath'
mkdir -p "$C/x" && g sm-foreach-displaypath "$C/x" git submodule foreach 'echo "$displaypath"'
g sm-update-back "$C" git submodule update
g sm-status-after-update "$C" git submodule status --recursive
# sync: change the .gitmodules URL, then sync
( cd "$C" && $ENV $T config -f .gitmodules submodule.midname.url ../mid-moved.git )
g sm-sync "$C" git submodule sync
g sm-sync-config "$C" git config --get submodule.midname.url
g sm-sync-sub-remote "$C/mid" git config --get remote.origin.url
g sm-sync-rec "$C" git submodule sync --recursive
g sm-sync-nested-remote "$C/mid/deps/leaf" git config --get remote.origin.url
( cd "$C" && $ENV $T checkout -q .gitmodules && $ENV $T submodule sync -q --recursive )
# ---- 6. update --remote honours branch =
( cd "$W/src/leaf" && echo three >> leaf.txt && $ENV $T commit -q -am 'leaf three' && $ENV $T push -q "$W/leaf.git" main )
g sm-update-remote "$C" git -c protocol.file.allow=always submodule update --remote abs
g sm-update-remote-status "$C" git status -s
g sm-update-remote-head "$C/abs" git log --oneline -1
# ---- 7. checkout/switch/reset/pull leave submodules alone by default
g co-old "$C" git -c advice.detachedHead=false checkout HEAD~2
g co-old-status "$C" git status
g co-old-sm "$C" git submodule status
g co-back "$C" git checkout main
g co-recurse "$C" git -c advice.detachedHead=false checkout --recurse-submodules HEAD~2
g co-recurse-sm "$C" git submodule status --recursive
g co-recurse-back "$C" git checkout --recurse-submodules main
g switch-recurse-cfg "$C" git -c submodule.recurse=true switch --detach HEAD~1
g switch-recurse-cfg-sm "$C" git submodule status
g switch-back "$C" git -c submodule.recurse=true switch main
g reset-hard-old "$C" git reset --hard HEAD~1
g reset-hard-old-sm "$C" git submodule status
g reset-hard-old-st "$C" git status -s
g reset-hard-back "$C" git reset --hard ORIG_HEAD
g reset-hard-recurse "$C" git reset --hard --recurse-submodules HEAD
g reset-hard-recurse-sm "$C" git submodule status
# rm of a submodule
g rm-sub "$C" git rm abs
g rm-sub-status "$C" git status
g rm-sub-gitmodules "$C" cat .gitmodules
dump after-rm "$C"
g rm-sub-cached-restore "$C" git reset -q --hard
# ---- 8. relative URL resolution matrix (init only; no fetch)
mk_rel() { # mk_rel DIR REMOTEURL SUBURL
    rm -rf "$1"; mkdir -p "$1"; ( cd "$1" && $ENV $T init -q && printf '[submodule "s"]\n\tpath = s\n\turl = %s\n' "$3" > .gitmodules && \
      $ENV $T update-index --add --cacheinfo 160000,$(cd "$W/src/leaf" && $ENV $T rev-parse HEAD),s && \
      { [ -z "$2" ] || $ENV $T remote add origin "$2"; } )
}
i=0
for remote in "" "file://$W/top.git" "file://$W/top" "$W/top.git" "$W/top/" "https://h.example/o/top.git" "https://h.example/o/top" "https://h.example/o/top/" "https://h.example/top" "https://h.example" "git@h.example:o/top.git" "h.example:top.git" "h.example:top" "h.example:o/p/top" "ssh://u@h.example:2222/o/top.git" "git://h.example/o/top.git" "../top.git" "./top" "top"; do
  for url in "../x.git" "./x.git" "../../y/x.git" "../../../x.git" "./x" "../x/" ".././x" "../x/./y" "../x/../y"; do
    i=$((i+1)); d=$W/rel/$i; mk_rel "$d" "$remote" "$url"
    n=$((n+1)); f=$(printf '%s/steps/%03d-rel-%d' "$OUT" "$n" "$i")
    printf 'remote=%s\nurl=%s\n' "$remote" "$url" > "$f.argv"
    ( cd "$d" && $ENV $T submodule init ) > "$f.out" 2> "$f.err"; echo $? > "$f.rc"
    ( cd "$d" && $ENV $T config --get submodule.s.url ) > "$f.resolved" 2>&1
  done
done
# a remote other than origin, picked by the current branch's upstream
mk_rel "$W/rel/up" "" "../x.git"; ( cd "$W/rel/up" && $ENV $T remote add up https://u.example/a/b.git && $ENV $T remote add origin https://o.example/c/d.git && \
  $ENV $T config branch.main.remote up && $ENV $T config branch.main.merge refs/heads/main )
g rel-upstream-remote "$W/rel/up" sh -c 'git submodule init && git config --get submodule.s.url'
# nested relative: leafsub's ../leaf.git resolves against mid's remote, not top's
g rel-nested "$C/mid" git config --get submodule.leafsub.url
# ---- 9. insteadOf: an https submodule URL rewritten to a local file URL
mkdir -p "$W/iof" && ( cd "$W/iof" && $ENV $T init -q --bare top2.git )
( cd "$W/src" && rm -rf top2 && $ENV $T init -q top2 && cd top2 && echo t > t && $ENV $T add t && \
  printf '[submodule "lf"]\n\tpath = lf\n\turl = https://forge.example/o/leaf.git\n' > .gitmodules && $ENV $T add .gitmodules && \
  $ENV $T update-index --add --cacheinfo 160000,$(cd "$W/src/leaf" && $ENV $T rev-parse HEAD~1),lf && $ENV $T commit -q -m t2 && $ENV $T push -q "$W/iof/top2.git" main )
g insteadof-clone "$W/iof" git -c protocol.file.allow=always -c "url.file://$W/.insteadOf=https://forge.example/o/" clone --recurse-submodules "file://$W/iof/top2.git" c2
g insteadof-config "$W/iof/c2" git config --get submodule.lf.url
g insteadof-sub-remote "$W/iof/c2/lf" git config --get remote.origin.url
g insteadof-noconfig-later "$W/iof/c2" git -c protocol.file.allow=always submodule update --init
g pushinsteadof-geturl "$W/iof/c2/lf" git -c url.ssh://push.example/.pushInsteadOf=https://forge.example/ -c url.zzz://never/.insteadOf=https://nomatch/ remote get-url --push origin
# ---- 10. hostile and odd inputs (each a fresh superproject pushed to a bare repo)
hostile() { # hostile NAME GITMODULES_TEXT GITLINK_PATH
    local name=$1 text=$2 path=$3
    rm -rf "$W/h/$name" "$W/h/$name.git"; mkdir -p "$W/h"
    $ENV $T init -q --bare "$W/h/$name.git"
    ( cd "$W/h" && $ENV $T init -q "$name" && cd "$name" && echo x > x && $ENV $T add x && \
      { [ -z "$text" ] || { printf '%s' "$text" > .gitmodules && $ENV $T add .gitmodules; }; } && \
      { [ -z "$path" ] || $ENV $T update-index --add --cacheinfo 160000,$(cd "$W/src/leaf" && $ENV $T rev-parse HEAD),"$path"; } && \
      $ENV $T commit -q -m h && $ENV $T push -q "$W/h/$name.git" main ) > "$OUT/hostile-$name.build" 2>&1
    g "hostile-$name-clone" "$W/h" git -c protocol.file.allow=always clone --recurse-submodules "file://$W/h/$name.git" "c-$name"
    [ -d "$W/h/c-$name" ] && dump "hostile-$name" "$W/h/c-$name"
    g "hostile-$name-plain" "$W/h" git clone -q "file://$W/h/$name.git" "p-$name"
    [ -d "$W/h/p-$name" ] && g "hostile-$name-update" "$W/h/p-$name" git -c protocol.file.allow=always submodule update --init
    [ -d "$W/h/p-$name" ] && g "hostile-$name-status" "$W/h/p-$name" git status --porcelain
    [ -d "$W/h/p-$name" ] && g "hostile-$name-smstatus" "$W/h/p-$name" git submodule status
}
LEAF="file://$W/leaf.git"
hostile escape-path "$(printf '[submodule "e"]\n\tpath = ../escape\n\turl = %s\n' "$LEAF")" "inside"
hostile dotdot-name "$(printf '[submodule "../evil"]\n\tpath = evil\n\turl = %s\n' "$LEAF")" "evil"
hostile dotdot-name-mid "$(printf '[submodule "a/../../evil"]\n\tpath = evil\n\turl = %s\n' "$LEAF")" "evil"
hostile dash-url "$(printf '[submodule "d"]\n\tpath = d\n\turl = -oProxyCommand=false\n')" "d"
hostile dash-path "$(printf '[submodule "d"]\n\tpath = -d\n\turl = %s\n' "$LEAF")" "-d"
hostile no-entry "" "orphan"
hostile stale-entry "$(printf '[submodule "s"]\n\tpath = s\n\turl = %s\n' "$LEAF")" ""
hostile invalid-config "$(printf '[submodule "bad"\n\tpath = bad\n\turl = %s\n' "$LEAF")" "bad"
hostile case-collide "$(printf '[submodule "A"]\n\tpath = A\n\turl = %s\n[submodule "a"]\n\tpath = a\n\turl = %s\n' "$LEAF" "$LEAF")" "A"
( cd "$W/h/case-collide" && $ENV $T update-index --add --cacheinfo 160000,$(cd "$W/src/leaf" && $ENV $T rev-parse HEAD),a && $ENV $T commit -q -m h2 && $ENV $T push -q -f "$W/h/case-collide.git" main ) >> "$OUT/hostile-case-collide.build" 2>&1
g hostile-case-collide-clone2 "$W/h" git -c protocol.file.allow=always clone --recurse-submodules "file://$W/h/case-collide.git" c-case2
hostile missing-url "$(printf '[submodule "m"]\n\tpath = m\n')" "m"
hostile name-slash "$(printf '[submodule "a/b"]\n\tpath = deep/b\n\turl = %s\n' "$LEAF")" "deep/b"
hostile dotgit-path "$(printf '[submodule "g"]\n\tpath = .git/x\n\turl = %s\n' "$LEAF")" ""
# a commit missing on the submodule's remote
rm -rf "$W/h/missing" "$W/h/missing.git"; $ENV $T init -q --bare "$W/h/missing.git"
( cd "$W/h" && $ENV $T init -q missing && cd missing && echo x > x && $ENV $T add x && \
  printf '[submodule "m"]\n\tpath = m\n\turl = %s\n' "$LEAF" > .gitmodules && $ENV $T add .gitmodules && \
  $ENV $T update-index --add --cacheinfo 160000,1111111111111111111111111111111111111111,m && $ENV $T commit -q -m h && $ENV $T push -q "$W/h/missing.git" main ) > "$OUT/hostile-missing.build" 2>&1
g hostile-missing-commit-clone "$W/h" git -c protocol.file.allow=always clone --recurse-submodules "file://$W/h/missing.git" c-missing
[ -d "$W/h/c-missing" ] && dump hostile-missing "$W/h/c-missing"
# ---- 11. versions and the environment
g version "$W" git --version
cp /env/environment.py "$OUT/environment.py"
echo "PROBE DONE $n steps"
