"""Docker integration regression: run after building the Compose tools image."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ToolsContainerTests(unittest.TestCase):
    def test_first_run_for_numeric_host_users(self):
        for user in ("1000:1000", "501:20"):
            with self.subTest(user=user):
                result = subprocess.run(
                    ["docker", "compose", "-f", "deployment/docker/compose.yaml",
                     "run", "--rm", "--no-deps", "--user", user, "tools", "sh", "-ec",
                     'test "$(stat -c %u "$XDG_RUNTIME_DIR")" = "$(id -u)"; '
                     'test "$(stat -c %a "$XDG_RUNTIME_DIR")" = 700; '
                     'dotnet --info; dotnet --help; '
                     'dotnet new console --no-restore -o /tmp/startup-check'],
                    cwd=ROOT, capture_output=True, text=True, timeout=120)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        lifecycle = r'''
mkdir /tmp/checks
cat > /tmp/checks/child <<'SH'
#!/bin/sh
printf '%s\n%s\n' "$XDG_RUNTIME_DIR" "$PWD" > /tmp/checks/paths
if [ "$1" = signal ]; then
    trap 'echo received > /tmp/checks/signal; exit 0' TERM
    while :; do sleep 0.1; done
fi
exit 23
SH
sh /tools-entrypoint.sh sh /tmp/checks/child normal &
parent=$!
status=0
wait "$parent" || status=$?
test "$status" = 23
while IFS= read -r path; do test ! -e "$path"; done < /tmp/checks/paths
rm /tmp/checks/paths
sh /tools-entrypoint.sh sh /tmp/checks/child signal &
parent=$!
attempt=0
while [ ! -f /tmp/checks/paths ]; do
    attempt=$((attempt + 1)); test "$attempt" -lt 200; sleep 0.1
done
sleep 0.2
kill -TERM "$parent"
status=0
wait "$parent" || status=$?
test "$status" = 143
test -f /tmp/checks/signal
while IFS= read -r path; do test ! -e "$path"; done < /tmp/checks/paths
printf '#!/bin/sh\nexit 1\n' > /tmp/checks/mktemp
chmod 700 /tmp/checks/mktemp
status=0
PATH=/tmp/checks:$PATH sh /tools-entrypoint.sh touch /tmp/checks/unexpected 2>/tmp/checks/error || status=$?
test "$status" = 1
test ! -e /tmp/checks/unexpected
grep -q 'cannot create private runtime directory' /tmp/checks/error
'''
        result = subprocess.run(
            ["docker", "compose", "-f", "deployment/docker/compose.yaml",
             "run", "--rm", "--no-deps", "tools", "sh", "-ec", lifecycle],
            cwd=ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
