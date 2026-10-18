# Upstream dependency timeouts

## Symptoms
Gateway timeouts (504) climbing. The upstream dependency is slow or unresponsive; our service is fine.

## Steps
- Raise upstream timeouts carefully so slow responses don't cascade into retries.
- Enable a circuit breaker so a sick upstream fails fast instead of hanging workers.
- Shed load or add backpressure if the upstream can't recover quickly.

## Rollback
Restore previous timeout values and disable the circuit breaker overrides.

## Risk
Medium. Longer timeouts hold workers longer; watch worker pool saturation.
