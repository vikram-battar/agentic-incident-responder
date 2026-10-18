# HTTP 5xx spike after a deploy

## Symptoms
5xx rate jumps within minutes of a release. Error logs show HTTP 500s correlated with the new version.

## Steps
- Rollback to the previous release immediately if the 5xx rate keeps climbing.
- Freeze further deploys until the bad release is identified.
- Diff the release: config changes, migrations, and dependency bumps.
- Check the error budget burn and page the owning team if it keeps burning.

## Rollback
The rollback itself is the fix; keep the previous release pinned until root cause is found.

## Risk
Medium. Rollbacks are routine but briefly flap traffic.
