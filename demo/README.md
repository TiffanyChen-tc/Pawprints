# Demo Walkthrough

1. Start and verify the stack:

```pwsh
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 demo
```

2. Open:

```text
http://localhost:8080
```

3. Log in with the local demo credentials:

```text
demo@pawprints.local
demo123
```

If an older local database already has `demo@pawprints.local` with a previous password, seed fails through the normal Auth API. Use a fresh local data set or override `PAWPRINTS_DEMO_EMAIL` for that run.

4. Check the Timeline for recent Pawprints, open an entry with an image, use Search for `demo`, and open Analytics for the current month or last 30 days.

5. Stop the stack without deleting demo data:

```pwsh
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 down
```
