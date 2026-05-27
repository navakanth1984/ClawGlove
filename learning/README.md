# Autonomous Learning Engine

Closes the loop on the routing lifecycle by observing outcomes and tuning the policies.

- `routing_optimizer.py`: Subscribes to trace events to correlate `ROUTE_SELECTED` decisions with terminal outcomes.
- `trust_calibrator.py`: Observes reputation trends and tunes trust clamping.
- `policy_recommender.py`: Recommends new tuned weights to `policies/recommendations/routing-weights-recommended.yaml`.
