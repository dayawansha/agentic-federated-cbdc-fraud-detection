# Debug Session: `kafka-topics-missing`

- Status: OPEN
- Started: 2026-06-27
- Symptom: The two Kafka topics that were previously visible on the single broker are no longer visible in Kafka UI.
- Expected: The broker should show the expected topics, and Kafka UI should display them.

## Hypotheses

1. Kafka is healthy, but the topics were not recreated after the recent restart/rebuild.
2. The topics still exist on the broker, but Kafka UI is not refreshing or is filtering them out.
3. Producer/consumer services expect `transactions.events` and `fraud.alerts`, but no successful topic creation or publish has happened yet.
4. Kafka UI metadata is stale or incomplete after the restart, even though broker state is correct.

## Evidence Log

- `docker exec infrastructure-kafka-1 kafka-topics --bootstrap-server localhost:9092 --list` returns only `__consumer_offsets`.
- Kafka UI API at `/kafka-ui/api/clusters` reports:
  - `brokerCount: 1`
  - `topicCount: 1`
  - `status: online`
- This confirms Kafka UI and the broker agree that only the internal Kafka topic currently exists.
- `infrastructure/docker-compose.yml` configures topic names (`transactions.events`, `fraud.alerts`) for services, but does not define any Compose startup step that creates those topics.
- The repository Helm template does include explicit topic creation commands for both topics, which indicates topic bootstrapping exists for Helm deployment but not for the current Compose deployment.
- The Kafka broker in `infrastructure/docker-compose.yml` has no mounted data volume, so a clean rebuild/recreate can discard previously existing application topics.
- Broker config shows `auto.create.topics.enable=true`, so application topics may reappear only after a producer/client actually triggers creation.

## Fix Log

- Added Kafka data persistence to the `kafka` service with a named volume at `/var/lib/kafka/data`.
- Added a `kafka-topic-init` Compose service that waits for broker availability and creates:
  - `transactions.events`
  - `fraud.alerts`
- Ran the topic-init step to recreate the missing topics immediately.

## Verification

- Verified broker and Kafka UI both show only one topic at the moment: Kafka's internal `__consumer_offsets`.
- Missing application topics are not currently a dashboard rendering bug.
- Post-fix broker topic list now returns:
  - `__consumer_offsets`
  - `fraud.alerts`
  - `transactions.events`
- Post-fix Kafka UI API `/kafka-ui/api/clusters` reports `topicCount: 3`.
- Post-fix Kafka UI API `/kafka-ui/api/clusters/federated-fraud-kafka/topics` lists both application topics with healthy single-partition metadata.
