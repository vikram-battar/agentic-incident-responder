# CPU throttling under load

## Symptoms
p99 latency climbs while CPU sits pinned at its limit. Kernel reports CPU throttling windows.

## Steps
- Scale out replicas to spread load across more CPU shares.
- Raise the CPU limit for the container to match observed p95 usage.
- Profile for hot loops or accidental busy-waiting before throwing hardware at it.

## Rollback
Scale back in and restore the previous CPU limit.

## Risk
Medium. Scaling out costs money; raising limits is low risk.
