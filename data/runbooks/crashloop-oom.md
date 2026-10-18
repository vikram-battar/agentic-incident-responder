# CrashLoopBackOff from OOMKilled

## Symptoms
Pod restarts repeatedly (CrashLoopBackOff). Container events show OOMKilled - the kernel killed the process when it exceeded its memory cgroup limit.

## Steps
- Confirm OOMKilled in the container events and check which process grew past the limit.
- Increase the container memory limit to match the workload's steady-state usage plus headroom.
- Roll back the recent deploy if memory growth started right after a release.
- Add a memory-based autoscaler or vertical pod autoscaler so limits track real usage.

## Rollback
Revert the memory limit change or roll back the deploy that introduced the growth.

## Risk
Medium. Raising limits is safe; rolling back a deploy needs a deploy freeze window.
