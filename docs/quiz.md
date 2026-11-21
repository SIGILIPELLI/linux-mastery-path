---
title: "Final Quiz"
description: "Test what you have learned across all four levels of Linux Mastery Path with a 18-question final quiz."
---

# Final Quiz

18 questions drawn from all four levels of this course. You need **70% (13 out of 18)** to pass —
you can retake it as many times as you like. Your best result is saved in this browser.

<div id="mp-quiz-root"></div>

<script type="application/json" id="mp-quiz-data">
[
  {
    "question": "A directory has mode 311 (d-wx--x--x) and you are its owner. `ls project` fails with 'Permission denied' but `cat project/notes.txt` works. Why?",
    "options": [
      "The owner can never list a directory",
      "cat bypasses permissions",
      "There is no read bit, so listing names is denied, but execute lets you traverse into it by name",
      "The file is world-writable"
    ],
    "correctIndex": 2,
    "explanation": "Read on a directory lists names; execute allows access by name. Verified: chmod 311 gives d-wx--x--x."
  },
  {
    "question": "With umask 022, what modes do a new file and a new directory get? With umask 077?",
    "options": [
      "Both 644",
      "022: 755 and 644. 077: 700 and 600",
      "Both 755",
      "022: file 644, directory 755. 077: file 600, directory 700"
    ],
    "correctIndex": 3,
    "explanation": "New files start at 666 and directories at 777, minus the umask. Verified by creating them: 644/755 and 600/700."
  },
  {
    "question": "A shared project directory should make every new file belong to the team group automatically. Which setting?",
    "options": [
      "SUID on the directory",
      "chmod 777",
      "SGID on the directory (chmod 2775, group set to the team): drwxrwsr-x",
      "The sticky bit"
    ],
    "correctIndex": 2,
    "explanation": "SGID on a directory makes new files inherit the directory's group. Verified: chmod 2775 shows drwxrwsr-x."
  },
  {
    "question": "Anyone may create files in /tmp but only a file's owner may delete it. Which bit, and how does it appear?",
    "options": [
      "The sticky bit, shown as t: drwxrwxrwt (mode 1777)",
      "SGID, shown as S",
      "No special bit is needed",
      "SUID, shown as s"
    ],
    "correctIndex": 0,
    "explanation": "Verified: chmod 1777 gives drwxrwxrwt."
  },
  {
    "question": "`ls -l /usr/bin/passwd` shows -rwsr-xr-x root root. What does the s mean for a normal user running it?",
    "options": [
      "The user becomes root permanently",
      "The program runs with the file owner's (root's) UID, so it can update /etc/shadow",
      "The file is a symlink",
      "Only root can run it"
    ],
    "correctIndex": 1,
    "explanation": "SUID applies for the lifetime of that process only."
  },
  {
    "question": "You run `ln original.txt hardlink.txt` and `ln -s original.txt symlink.txt`, then `rm original.txt`. What happens?",
    "options": [
      "Both still work",
      "Both break",
      "cat hardlink.txt still works (the inode survives with 1 link); the symlink is broken",
      "Only the symlink works"
    ],
    "correctIndex": 2,
    "explanation": "A hard link is another name for the same inode; a symlink stores a path. Verified by running the commands: link count 2 → 1, hardlink prints hello, symlink broken."
  },
  {
    "question": "`ls /nonexistent 2>&1 > cmd.log` leaves cmd.log empty and prints the error to the screen. Why?",
    "options": [
      "The file was read-only",
      "stderr was duplicated onto the terminal first; only afterwards was stdout redirected to the file",
      "2>&1 is invalid",
      "ls writes errors to stdout"
    ],
    "correctIndex": 1,
    "explanation": "Redirections apply left to right. `> cmd.log 2>&1` captures both. Verified by running both orders."
  },
  {
    "question": "A process shows state Z in ps and `kill -9` does nothing. What is it, and what removes it?",
    "options": [
      "A hung process; wait",
      "An uninterruptible sleep; send SIGKILL again",
      "A stopped process; send SIGCONT",
      "A zombie: it already exited, so there's nothing to signal; the parent must collect its status (or die, so init reaps it)"
    ],
    "correctIndex": 3,
    "explanation": "A zombie is just an exit-status record."
  },
  {
    "question": "A process is stuck in state D (uninterruptible sleep) on disk I/O. Will SIGKILL end it immediately?",
    "options": [
      "No: it can't be killed until the I/O completes",
      "Yes, always",
      "Only for root",
      "Only with SIGTERM"
    ],
    "correctIndex": 0,
    "explanation": "The kernel considers the operation too delicate to abort."
  },
  {
    "question": "`free -h` shows 1.0Gi free but 3.3Gi available. Is the system low on memory?",
    "options": [
      "Yes: memory is leaking",
      "No: much of it is reclaimable page cache (buff/cache), which counts as available",
      "Yes: swap is full",
      "It depends on the CPU"
    ],
    "correctIndex": 1,
    "explanation": "Look at available, not free."
  },
  {
    "question": "A service must run 'every 5 minutes' without overlapping itself if a run takes 6 minutes. Which mechanism fits best?",
    "options": [
      "A cron entry every 5 minutes",
      "A systemd timer using OnUnitActiveSec= (runs after the previous run finished)",
      "A while-true loop with &",
      "at now + 5 minutes"
    ],
    "correctIndex": 1,
    "explanation": "OnUnitActiveSec counts from the end of the last run. Output also goes to journald."
  },
  {
    "question": "You added a new line to /etc/fstab. How do you check it without rebooting?",
    "options": [
      "Run `sudo mount -a`, which attempts every entry as boot would",
      "Run fsck on /",
      "Run `mount -l`",
      "Reboot and watch"
    ],
    "correctIndex": 0,
    "explanation": "A bad non-root entry can drop the next boot into an emergency shell."
  },
  {
    "question": "`/etc/resolv.conf` says `nameserver 127.0.0.53`. Where do DNS queries really go?",
    "options": [
      "Nowhere: it is broken",
      "To the internet's root servers directly",
      "To systemd-resolved's local stub, which forwards them to the upstream server shown by `resolvectl status`",
      "To /etc/hosts only"
    ],
    "correctIndex": 2,
    "explanation": "nsswitch.conf's hosts: files dns line decides that /etc/hosts is checked first."
  },
  {
    "question": "A service is listening on port 9090 (`ss -tln` shows it), but remote connections time out while local ones work. What is the most likely cause?",
    "options": [
      "The service isn't started",
      "DNS is wrong",
      "The kernel is too old",
      "A firewall rule dropping the port (check nft list ruleset / iptables)"
    ],
    "correctIndex": 3,
    "explanation": "The capstone's Fault 2: the socket is LISTENing, yet packets never reach it."
  },
  {
    "question": "`curl` returns HTTP status 000 for your service. What does it tell you?",
    "options": [
      "The server returned 500",
      "No HTTP exchange took place: nothing accepted the connection (service stopped, wrong port or firewall), so check the service and socket first",
      "The TLS certificate expired",
      "The server returned 404"
    ],
    "correctIndex": 1,
    "explanation": "Status 000 means curl got no HTTP response."
  },
  {
    "question": "Which two kernel mechanisms make a process look like a container, and what does each do?",
    "options": [
      "Namespaces limit what it can see (PID, mount, UTS, network, user…); cgroups limit what it can use (CPU, memory…)",
      "SELinux and AppArmor",
      "Hypervisor and VM",
      "Chroot and sudo"
    ],
    "correctIndex": 0,
    "explanation": "A container is a normal process on the host kernel."
  },
  {
    "question": "A process in a cgroup with memory.max=50M tries to allocate more. What happens?",
    "options": [
      "The kernel OOM-kills it inside the cgroup (CONSTRAINT_MEMCG); the host keeps running",
      "The whole system freezes",
      "The allocation silently succeeds",
      "It gets swap"
    ],
    "correctIndex": 0,
    "explanation": "dmesg shows 'Memory cgroup out of memory: Killed process'."
  },
  {
    "question": "Why does `iptables -V` print (nf_tables) on modern distros?",
    "options": [
      "iptables is the old kernel subsystem",
      "Netfilter was removed",
      "iptables is a compatibility front end that translates rules into nftables, both configuring netfilter's hooks",
      "nftables is just a rename"
    ],
    "correctIndex": 2,
    "explanation": "Neither tool is netfilter itself."
  }
]
</script>

## Coding challenges

Try these on your own computer, then compare your output. Nothing you write is sent anywhere.

### Redirection order

Using the emit function (writes one line to stdout and one to stderr), write redirections so that: A) both streams end up in both.log, B) stdout goes to out.log and stderr to err.log, C) demonstrate the common mistake by writing `2>&1` BEFORE `> wrong.log`, capturing what leaks to the terminal with $( ). Print the results exactly as shown in the expected output.

**Starter code**

```bash
emit() { echo "to stdout"; echo "to stderr" >&2; }

# A: send both streams into both.log
emit # your redirection here
echo "A: $(wc -l < both.log | tr -d ' ') lines"

# B: stdout to out.log, stderr to err.log
emit # your redirection here
echo "B: out=[$(cat out.log)] err=[$(cat err.log)]"

# C: wrong order
leaked=$(emit) # your redirection here
echo "C: leaked=[$leaked] wrong.log=[$(cat wrong.log)]"
```

**Expected output**

```text
A: 2 lines
B: out=[to stdout] err=[to stderr]
C: leaked=[to stderr] wrong.log=[to stdout]
```

<details><summary>Show solution and explanation</summary>

<pre><code>emit() { echo &quot;to stdout&quot;; echo &quot;to stderr&quot; &gt;&amp;2; }

# A: send both streams into both.log
emit &gt; both.log 2&gt;&amp;1
echo &quot;A: $(wc -l &lt; both.log | tr -d &#x27; &#x27;) lines&quot;

# B: stdout to out.log, stderr to err.log
emit &gt; out.log 2&gt; err.log
echo &quot;B: out=[$(cat out.log)] err=[$(cat err.log)]&quot;

# C: wrong order - stderr is duplicated onto the terminal (here, captured by $( ))
leaked=$(emit 2&gt;&amp;1 &gt; wrong.log)
echo &quot;C: leaked=[$leaked] wrong.log=[$(cat wrong.log)]&quot;
</code></pre>

<p>`&gt; file 2&gt;&amp;1` points fd 1 at the file and then fd 2 at wherever fd 1 now points. With `2&gt;&amp;1 &gt; file`, fd 2 is duplicated onto the terminal first, so errors still leak. Verified by running the solution in bash: output matches.</p>
</details>

### Hard link versus symlink

Create original.txt containing hello, a hard link hardlink.txt and a symlink symlink.txt. Print the link count of original.txt, delete the original, then show whether the hard link and the symlink still work and the link count that remains.

**Starter code**

```bash
echo hello > original.txt
# create a hard link and a symlink to original.txt

echo "links before: $(ls -l original.txt | awk '{print $2}')"
rm original.txt
echo "hardlink: $(cat hardlink.txt)"
if [ -e symlink.txt ]; then echo "symlink: works"; else echo "symlink: broken"; fi
echo "links after: $(ls -l hardlink.txt | awk '{print $2}')"
```

**Expected output**

```text
links before: 2
hardlink: hello
symlink: broken
links after: 1
```

<details><summary>Show solution and explanation</summary>

<pre><code>echo hello &gt; original.txt
ln original.txt hardlink.txt
ln -s original.txt symlink.txt
echo &quot;links before: $(ls -l original.txt | awk &#x27;{print $2}&#x27;)&quot;
rm original.txt
echo &quot;hardlink: $(cat hardlink.txt)&quot;
if [ -e symlink.txt ]; then echo &quot;symlink: works&quot;; else echo &quot;symlink: broken&quot;; fi
echo &quot;links after: $(ls -l hardlink.txt | awk &#x27;{print $2}&#x27;)&quot;
</code></pre>

<p>A hard link is a second directory entry for the same inode (link count 2), so the data survives rm. A symlink is a separate tiny file holding a path, which breaks when the target disappears. Verified by running the solution in bash: output matches.</p>
</details>
