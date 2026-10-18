# Database connection exhaustion

## Symptoms
"too many connections" / pool exhausted. Writes and reads start failing even though the database itself is healthy.

## Steps
- Kill long-idle connections to relieve immediate pressure.
- Raise max_connections within what the instance can actually handle.
- Failover to the read replica or promote a standby if the primary is saturated.

## Rollback
Fail back to the original primary once connection counts normalize.

## Risk
High. Failover can cause brief write unavailability and replication lag - get human approval first.
