# Known Issues

## 🔴 Intermittent connectivity loss when FORWARD policy = DROP

**Status:** Unresolved, investigation paused (2026-08-02).

**Symptom:** When setting the `FORWARD` chain default policy to `DROP`
(with the `nestnet-allow` allowlist rules and an `ESTABLISHED,RELATED`
accept rule in place), one specific LAN device intermittently loses
internet access — sometimes immediately after DROP, sometimes after
a delay, not on every attempt.

**Notable detail:** only one device on the network was observed losing
connectivity during testing — every other device (cameras, TVs, Echo
devices, etc.) kept working normally throughout. This is a real clue
that hasn't been explained yet: it points to something specific about
that device's traffic pattern or timing (e.g. it was the one actively
being used to test), rather than a general allowlist/rule problem
affecting all devices equally.

**Investigated and ruled out:**
- IPv6: `ip6tables` FORWARD policy is `ACCEPT`, and the affected device
  has no IPv6 default route — not the cause.
- AdGuard Home: found and fixed a 316GB rotated query log file
  (`querylog.json.1`) that was likely causing DNS lookup slowness.
  Retention was set to 30 days and logs were cleared. Cutoffs continued
  after this fix, so it was a real bug but not the (sole) root cause.
- Confirmed via tcpdump that at least once, the allowlist ACCEPT rule
  matched correctly and traffic passed fine under DROP — so the issue
  is not 100% reproducible, which points to either a race condition
  or a timing/coordination issue during manual multi-terminal testing.

**Next steps when resuming:**
- Reproduce with a single automated script (not manual multi-terminal
  steps) to remove human timing/coordination error as a variable.
- Capture a full tcpdump trace (not just DNS, all traffic) during a
  confirmed failure, with more time margin, ideally not on a device
  someone is depending on in the moment.
- Investigate why only one device was ever affected — check if that
  device has any distinguishing traffic pattern, DHCP lease behavior,
  or interface quirk vs. the others.

**Current safe state:** `FORWARD` policy is left at `ACCEPT` (open,
no allowlist enforcement) until this is resolved and confirmed stable.
