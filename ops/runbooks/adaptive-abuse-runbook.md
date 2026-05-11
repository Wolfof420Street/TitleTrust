# Adaptive Abuse Response Runbook

## Purpose

This runbook covers TitleTrust's adaptive abuse detection path, including quarantine, challenge escalation, and block outcomes.

## Signals to Watch

- `titletrust_abuse_assessments_total`
- `titletrust_abuse_blocks_total`
- `titletrust_abuse_score`
- `X-Abuse-Action` response headers
- `X-Correlation-ID` propagation

## Triage Flow

1. Confirm whether the activity is tenant-bound, device-bound, or correlation-ID clustered.
2. Review the latest abuse assessment action and score.
3. Check whether the request fingerprint is quarantined or known-threat tagged.
4. Verify whether the associated session risk level has moved into `HIGH` or `CRITICAL`.
5. Determine whether the event is a genuine burst, credential stuffing attempt, or replay pattern.

## Immediate Actions

- `allow`: no action required unless frequency spikes.
- `throttle`: monitor for clustering and escalate if repeated.
- `challenge`: require step-up verification.
- `quarantine`: isolate the fingerprint and review tenant activity.
- `block`: confirm the event as hostile or automated abuse, then preserve evidence.

## Evidence Collection

- Correlation ID
- Tenant ID
- Device ID
- Request fingerprint
- Abuse assessment action and score
- Session risk level
- Audit export if the request touched a protected workflow

## Escalation Criteria

- Multiple fingerprints from the same tenant trip challenge or quarantine within 10 minutes.
- Abuse block rate remains elevated for 5 minutes.
- Token replay attempts coincide with abuse detections.
- CSP violations or impossible travel signals appear in the same correlation window.

## Recovery

- Clear the quarantine only after confirming the source is legitimate.
- Rotate affected tokens if replay or compromise is suspected.
- Preserve the correlation trail for incident review.
- Update the threat intelligence store if the event was malicious.

## Post-Incident Review

- Compare P50/P95/P99 request latency before and after the incident.
- Check whether the challenge threshold needs tuning.
- Confirm alert coverage captured the event.
