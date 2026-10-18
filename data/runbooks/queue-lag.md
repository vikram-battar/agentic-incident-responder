# Growing queue / consumer lag

## Symptoms
Consumer lag climbs, backlog grows faster than workers drain it. Throughput below arrival rate.

## Steps
- Scale up workers to close the gap between arrival and drain rates.
- Check for poison messages blocking partitions before scaling blindly.
- Add lag alerting so the next backlog pages before it gets this big.

## Rollback
Scale workers back down once the backlog is drained.

## Risk
Low to medium. Scaling workers is safe; poison messages need care.
