# Disk pressure / volume full

## Symptoms
Writes fail with "no space left on device". The node reports DiskPressure and may start evicting pods.

## Steps
- Clear old logs and temp files to buy immediate headroom.
- Expand the volume or move the workload to a node with free disk.
- Add disk-usage alerting well before the 90% mark so this pages earlier next time.

## Rollback
Shrink back or restore the previous volume size once pressure is relieved.

## Risk
Medium. Deleting the wrong files hurts; stick to rotated logs and tmp.
