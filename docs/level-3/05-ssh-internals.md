---
description: "Host keys vs user keys, real key fingerprints, ssh-agent holding a loaded identity, and why host key permissions matter at the OS level."
---

# 05 · SSH Internals: Keys, Agents & the Protocol

SSH is used constantly and understood loosely — "it uses keys" is usually as far as the mental model goes. This
lesson separates the **two completely different kinds of key** SSH uses, shows what `ssh-agent` is actually
holding in memory, and ties key-file permissions back to the permission model from Level 1.

## Host keys vs user keys: proving identity in two different directions

A **host key** belongs to a *server* and proves "you are really talking to the machine you think you are" — it's
generated once (usually at first boot or package install) and almost never changes, which is exactly why SSH
warns loudly ("REMOTE HOST IDENTIFICATION HAS CHANGED") if it ever does: that warning exists specifically to catch
both legitimate re-provisioning and active man-in-the-middle attacks, and SSH can't tell those two causes apart on
its own. A **user key** belongs to a *person* (or an automation identity) and proves "this connection is really
authorized by whoever holds the matching private key" — the exact mechanism `ssh-copy-id` and `authorized_keys`
files are built around.

## Worked example: real host keys, permissions, and a freshly generated user key

```text
$ ls -la /etc/ssh/ssh_host_ed25519_key /etc/ssh/ssh_host_ed25519_key.pub
-rw------- 1 root root  411 Oct 22 23:28 ssh_host_ed25519_key
-rw-r--r-- 1 root root  100 Oct 22 23:28 ssh_host_ed25519_key.pub

$ ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
256 SHA256:scCYkeG0/Nr0HIeSsN53AUHJCqckaT9qoAmSWVjoyI0 root@lima-linuxlab (ED25519)

$ ssh-keygen -t ed25519 -f demokey -N "" -C "demo-key"
Generating public/private ed25519 key pair.
Your identification has been saved in demokey
The key fingerprint is:
SHA256:a3+oMQZ63VkpPbtGCXwBbUliK2JJAxwpw1LFgUDaO9A demo-key

$ eval $(ssh-agent -s)
Agent pid 257627
$ ssh-add demokey
Identity added: demokey (demo-key)
$ ssh-add -l
256 SHA256:a3+oMQZ63VkpPbtGCXwBbUliK2JJAxwpw1LFgUDaO9A demo-key (ED25519)
```

(Real output from this course's lab VM.) The host **private** key is `rw-------` (owner-only, enforced not just
by convention but checked by `sshd` itself, which refuses to use a key file with overly permissive permissions —
a direct, practical consequence of Level 1's permission lessons: a private key readable by other users defeats
the entire point of it being private). The matching **public** key is world-readable, as it should be — there is
nothing secret about a public key; its entire job is to be shared. `ssh-keygen -lf` computes a **fingerprint**
(a SHA-256 hash of the public key) rather than printing the full key material, which is why fingerprints, not raw
keys, are what people traditionally read aloud to verify a host's identity over a side channel. `ssh-add -l`
proves the agent is now holding the demo key's identity in memory — notably, the **private key file itself is no
longer needed on disk** for authentication to work from this point forward; the agent holds the loaded key and
performs the cryptographic signing operation on behalf of any SSH client that asks it to, without ever handing the
private key bytes back out.

## How It Actually Works

The reason `ssh-agent` exists at all, rather than every `ssh` invocation simply reading your private key file
directly, is to avoid re-entering a passphrase on every single connection (if the key is passphrase-protected) and
— more importantly for automation and agent-forwarding scenarios — to avoid the private key material ever
needing to leave the machine it was generated on. When you SSH *through* one machine to a second one with agent
forwarding enabled, the second machine's `sshd` sends a cryptographic challenge back through the chain to your
**original** agent, which signs it and returns the signature — your private key is never copied to the
intermediate or destination machine, only a signed proof that you hold it.

The SSH **protocol handshake** itself, at a conceptual level, layers two independent processes: first, key
exchange establishes a shared encryption key for the whole session (this is where the *host* key comes in — it
signs the key-exchange output so the client can verify it's negotiating with the real server, not an attacker
sitting in the middle) and sets up an encrypted, integrity-checked transport; only after that encrypted channel
exists does *user* authentication happen inside it — password, public key, or another configured method — which
is why a leaked password sent over SSH is still protected by the channel's encryption, something worth remembering
when reasoning about which secrets SSH actually protects and from whom.

## Common mistakes

- **Reusing one SSH key across many unrelated services and systems with no segmentation.** If that one private
  key is ever compromised, every system it was authorized against is compromised simultaneously — per-purpose or
  per-system keys limit the blast radius, at the cost of some extra key management.
- **Accepting a host key change warning without investigating.** It's tempting to run `ssh-keygen -R <host>` and
  move on the moment this warning appears, but as covered above, this exact warning is also what a real
  man-in-the-middle attack looks like from the client's side — confirm the change is expected (a re-provisioned
  server, a restored backup) before clearing it.
- **Setting private key file permissions wider than `600` and being confused when `sshd`/`ssh` refuses to use
  it.** This isn't a bug — both the client and server-side tooling actively check and reject overly-permissive
  private key file modes as a safety measure, tying directly back into Level 1's permission model.

## Exercise

Generate a test SSH keypair with `ssh-keygen -t ed25519 -f testkey -N ""`, compute its fingerprint with
`ssh-keygen -lf testkey.pub`, then deliberately `chmod 644 testkey` and try to use it with `ssh -i testkey ...`
against any host — confirm it's refused, then `chmod 600` it back and confirm it's accepted. Separately, start
`ssh-agent`, add the key, and run `ssh-add -l` before and after to see the identity appear and (after `ssh-add
-D`) disappear from the agent's memory.
