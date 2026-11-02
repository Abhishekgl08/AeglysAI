#!/bin/sh
set -eu
workspace=
runtime_dir=
child=
cleanup() {
    cd / || return
    [ -z "$workspace" ] || rm -rf -- "$workspace"
    [ -z "$runtime_dir" ] || rm -rf -- "$runtime_dir"
}
terminate() {
    trap '' INT TERM
    if [ -n "$child" ]; then
        kill -"$1" "$child" 2>/dev/null || true
        wait "$child" 2>/dev/null || true
    fi
    exit "$2"
}
trap cleanup EXIT
trap 'terminate TERM 143' TERM
trap 'terminate INT 130' INT
# Compose can run with a host UID absent from the container's user database.
# .NET named mutexes need a private, user-owned runtime directory in that case.
if ! runtime_dir=$(mktemp -d /tmp/aeglysai-runtime.XXXXXXXXXX); then
    echo 'tools: cannot create private runtime directory' >&2
    exit 1
fi
XDG_RUNTIME_DIR=$runtime_dir
export XDG_RUNTIME_DIR
# Isolated build outputs: never mix host and Linux bin/obj directories.
workspace=$(mktemp -d)
cd /repository
tar --exclude=.git --exclude=bin --exclude=obj --exclude=.local --exclude=research/results --exclude=./research/results -cf - . | tar -xf - -C "$workspace"
cd "$workspace"
ln -s /repository/.git .git
mkdir -p research
ln -s /results research/results
"$@" &
child=$!
status=0
wait "$child" || status=$?
exit "$status"
