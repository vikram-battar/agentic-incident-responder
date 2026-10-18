# CrashLoopBackOff from invalid configuration

## Symptoms
Container starts then exits immediately. Logs show invalid configuration or a missing required key.

## Steps
- Restore the missing config key or fix the malformed value.
- Redeploy with validated config; dry-run the config load first.
- Add config validation to CI so bad config never ships again.

## Rollback
Restore the previous known-good config version.

## Risk
Medium. A wrong value can be worse than a missing one - validate first.
