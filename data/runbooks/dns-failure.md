# DNS resolution failures

## Symptoms
"no such host" and DNS lookup failures for an upstream dependency. Affects a share of requests, not all.

## Steps
- Check CoreDNS / resolver health and recent config changes.
- Verify the DNS records for the failing hostname still resolve externally.
- Roll back the DNS change or resolver config that preceded the failures.

## Rollback
Restore the previous DNS records or resolver configuration.

## Risk
Medium. DNS changes propagate slowly; verify before and after.
