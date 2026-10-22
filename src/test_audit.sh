#!/bin/sh
# Builds a fixture tree and checks audit.sh's findings. Fixtures are hand-written (not from a real Linux system).
fail=0; here=$(cd "$(dirname "$0")" && pwd)
t=$(mktemp -d) || exit 1; cd "$t" || exit 1
mkdir -p tree/clean tree/shared tree/tmpish; chmod 755 tree tree/clean
echo data > tree/clean/ok.txt; chmod 644 tree/clean/ok.txt
echo x > tree/shared/leak.txt; chmod 666 tree/shared/leak.txt
chmod 777 tree/shared; chmod 1777 tree/tmpish
printf '#!/bin/sh\n' > tree/clean/helper; chmod 4755 tree/clean/helper
head -c 3145728 /dev/zero > tree/clean/big.bin
cat > passwd.fixture <<'P'
root:x:0:0:root:/root:/bin/bash
toor:x:0:0:backdoor:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
svc:x:105:105:service:/var/lib/svc:/bin/bash
alice:x:1001:1001:Alice:/home/alice:/bin/bash
P
check() { # name expected-substring
  if echo "$out" | grep -q -- "$2"; then echo "PASS  $1"; else echo "FAIL  $1  (missing: $2)"; fail=1; fi; }
out=$(sh "$here/audit.sh" -p passwd.fixture -d tree -m 2); rc=$?
check "extra uid0 account found"         "extra UID 0 account: toor"
check "system account with login shell"  "system account with a login shell: svc"
echo "$out" | grep -q "FINDING.*daemon" && { echo "FAIL  nologin daemon flagged"; fail=1; } || echo "PASS  nologin daemon account not flagged"
check "world-writable file found"        "world-writable file: tree/shared/leak.txt"
check "world-writable dir w/o sticky"    "directory without sticky bit: tree/shared"
echo "$out" | grep -q "tmpish" && { echo "FAIL  sticky dir wrongly flagged"; fail=1; } || echo "PASS  sticky world-writable dir not flagged"
check "setuid file found"                "setuid/setgid file: tree/clean/helper"
check "big file found (>2 MB)"           "file over 2 MB: tree/clean/big.bin"
[ "$rc" -eq 1 ] && echo "PASS  exit status 1 with findings" || { echo "FAIL  exit status was $rc"; fail=1; }
mkdir clean2; echo ok > clean2/a; chmod 644 clean2/a; printf 'root:x:0:0::/root:/bin/sh\n' > p2
out=$(sh "$here/audit.sh" -p p2 -d clean2); rc=$?
[ "$rc" -eq 0 ] && echo "PASS  exit status 0 on a clean tree" || { echo "FAIL  clean tree rc=$rc"; echo "$out"; fail=1; }
sh "$here/audit.sh" -d /nonexistent 2>/dev/null; [ $? -eq 2 ] && echo "PASS  exit 2 on bad directory" || { echo "FAIL  bad dir"; fail=1; }
echo "-- full report for the fixture:"; echo "$out" >/dev/null; sh "$here/audit.sh" -p passwd.fixture -d tree -m 2
cd /; rm -rf "$t"; exit $fail
