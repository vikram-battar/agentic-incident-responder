# Cache memory pressure / eviction storm

## Symptoms
Mass evictions, hit rate craters, origin load spikes as the cache stops absorbing traffic.

## Steps
- Raise maxmemory on the cache nodes to fit the working set.
- Add a cache shard to spread keys and reduce per-node pressure.
- Scale the cache tier out if the working set keeps growing.

## Rollback
Remove the added shard and restore the previous maxmemory setting.

## Risk
Medium. Resharding moves keys around; do it off-peak.
