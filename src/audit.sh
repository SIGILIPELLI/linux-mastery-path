#!/bin/sh
# audit.sh - a small, portable (POSIX sh) system audit. Usage: audit.sh [-p passwd_file] [-d dir] [-m max_mb]
# Exit status: 0 = no findings, 1 = findings, 2 = usage error.
passwd_file=/etc/passwd; scan_dir=.; max_mb=50; findings=0
while getopts "p:d:m:" opt; do
  case $opt in p) passwd_file=$OPTARG ;; d) scan_dir=$OPTARG ;; m) max_mb=$OPTARG ;; *) echo "usage: $0 [-p passwd] [-d dir] [-m max_mb]" >&2; exit 2 ;; esac
done
[ -d "$scan_dir" ] || { echo "no such directory: $scan_dir" >&2; exit 2; }
finding() { findings=$((findings + 1)); printf 'FINDING: %s\n' "$1"; }

printf 'host=%s os=%s kernel=%s arch=%s\n' "$(hostname | cut -d. -f1)" "$(uname -s)" "$(uname -r)" "$(uname -m)"

# 1. accounts with UID 0 other than root (works on files in passwd format; on macOS /etc/passwd has no real accounts)
extra=$(awk -F: '!/^#/ && NF >= 3 && $3 == 0 && $1 != "root" {print $1}' "$passwd_file")
for u in $extra; do finding "extra UID 0 account: $u"; done
# 2. empty password field / login shells for system accounts are not checkable without shadow; just report accounts with a login shell and UID < 1000
low=$(awk -F: '!/^#/ && NF >= 7 && $3 > 0 && $3 < 1000 && $7 !~ /(nologin|false)$/ {print $1}' "$passwd_file")
for u in $low; do finding "system account with a login shell: $u"; done
# 3. world-writable files and directories without the sticky bit
find "$scan_dir" -xdev -type f -perm -0002 2>/dev/null | sort | while read -r f; do printf 'FINDING: world-writable file: %s\n' "$f"; done > .ww_files.$$
find "$scan_dir" -xdev -type d -perm -0002 ! -perm -1000 2>/dev/null | sort | while read -r d; do printf 'FINDING: world-writable directory without sticky bit: %s\n' "$d"; done > .ww_dirs.$$
cat .ww_files.$$ .ww_dirs.$$; findings=$((findings + $(cat .ww_files.$$ .ww_dirs.$$ | wc -l))); rm -f .ww_files.$$ .ww_dirs.$$
# 4. setuid / setgid regular files
find "$scan_dir" -xdev -type f \( -perm -4000 -o -perm -2000 \) 2>/dev/null | sort > .sg.$$
while read -r f; do finding "setuid/setgid file: $f"; done < .sg.$$; rm -f .sg.$$
# 5. big files
find "$scan_dir" -xdev -type f -size +"${max_mb}"M 2>/dev/null | sort > .big.$$
while read -r f; do finding "file over ${max_mb} MB: $f"; done < .big.$$; rm -f .big.$$
# 6. listening TCP ports (informational; Linux ss if present, else lsof)
if command -v ss >/dev/null 2>&1; then listeners=$(ss -ltnH 2>/dev/null | awk '{print $4}' | sort -u | wc -l)
elif command -v lsof >/dev/null 2>&1; then listeners=$(lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | awk 'NR>1 {print $9}' | sort -u | wc -l)
else listeners=unknown; fi
printf 'info: listening TCP sockets: %s\n' "$(echo $listeners)"
printf 'summary: %s finding(s)\n' "$findings"
[ "$findings" -eq 0 ]
