# Deployment Strategy

## Purpose

Defines how ABBY is deployed, validated, and rolled back across environments.

## Environments

- **Dev** — local validation, feature testing
- **Staging** — integration & release candidate validation
- **Production** — live traffic

## Release Workflow

1. **Prepare release**
   - Confirm documentation updates
   - Validate migrations and schema changes

2. **Deploy to staging**
   - Run health checks
   - Validate scheduler startup
   - Validate critical flows (generation, delivery)

3. **Production deploy**
   - Canary or rolling deployment
   - Monitor critical metrics for 30–60 minutes

4. **Post‑deploy verification**
   - Run quick operational checklist
   - Verify no DLQ surge

## Health Checks

- Scheduler running & ticks healthy
- LLM generation responding within baseline
- Delivery success rate stable
- Database latency within threshold

## Rollback Criteria

- Scheduler failing to start
- DLQ volume spikes beyond baseline
- Generation latency > 3× baseline
- Error rate exceeds 2× baseline

## Rollback Procedure (Summary)

1. Revert to last known good release
2. Run health checks again
3. Document incident in INCIDENT_RESPONSE.md

## Reference

- [distribution/README.md](../distribution/README.md)
- [operations/INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md)
- [operations/OBSERVABILITY_RUNBOOK.md](OBSERVABILITY_RUNBOOK.md)
