# Debug Session: `kafka-ui-white-screen`

- Status: OPEN
- Started: 2026-06-27
- Symptom: Clicking the Kafka UI button from the dashboard opens a white screen.
- Expected: Kafka UI opens with its normal interface through the dashboard shortcut.

## Hypotheses

1. Kafka itself is running, but the Kafka UI container is down or unhealthy.
2. Kafka UI is healthy on its direct port, but the dashboard proxy path `/kafka-ui/` is misconfigured.
3. Kafka UI returns HTML, but its static assets or base path break behind the dashboard proxy and cause a white screen.
4. The dashboard is opening the wrong URL for Kafka UI in proxy mode.
5. Kafka UI starts, but cannot connect to Kafka internally and fails after initial page load.

## Evidence Log

- `docker ps` shows `infrastructure-kafka-1`, `infrastructure-kafka-ui-1`, and `infrastructure-fraud-dashboard-1` are all `Up`.
- `docker logs infrastructure-kafka-ui-1` shows repeated `Metrics updated for cluster: federated-fraud-kafka`, confirming Kafka UI can reach Kafka.
- `http://localhost:3000/kafka-ui/` returns `200` with Kafka UI HTML.
- `http://localhost:18080/` and `http://localhost:3000/kafka-ui/` both return HTML that sets `window.basePath = ''`.
- The returned Kafka UI HTML references root-relative assets such as:
  - `/assets/index-77be7e32.js`
  - `/assets/index-d9d582cd.css`
  - `/manifest.json`
  - `/favicon/favicon.ico`
- `http://localhost:3000/assets/index-77be7e32.js` returns the dashboard `index.html` (`Content-Type: text/html`) instead of the Kafka UI JavaScript bundle.
- `http://localhost:3000/kafka-ui/assets/index-77be7e32.js` returns `200` with `application/javascript`.

## Analysis

- Hypothesis 1 rejected: Kafka UI container is up.
- Hypothesis 5 rejected: Kafka UI can connect to Kafka, based on cluster metrics updates.
- Hypothesis 4 rejected: the dashboard button opens the expected proxied URL `/kafka-ui/`.
- Hypotheses 2 and 3 confirmed: the white screen is caused by proxy/base-path behavior. Kafka UI is being served behind `/kafka-ui/`, but its HTML still points the browser to root-relative assets, so the browser requests `/assets/...` and gets the dashboard app instead of Kafka UI assets.

## Fix Log

- Added `SERVER_SERVLET_CONTEXT_PATH: /kafka-ui` to the `kafka-ui` service in `infrastructure/docker-compose.yml`.
- Updated the dashboard nginx proxy in `bank-node/fraud-dashboard/nginx.conf` from `proxy_pass http://kafka-ui:8080/;` to `proxy_pass http://kafka-ui:8080;` so nginx preserves the `/kafka-ui` prefix when forwarding to Kafka UI.
- Rebuilt and restarted `kafka-ui` and `fraud-dashboard`.

## Verification

- `http://localhost:3000/kafka-ui/` now returns HTML with:
  - `window.basePath = '/kafka-ui'`
  - `/kafka-ui/assets/...`
  - `/kafka-ui/manifest.json`
  - `/kafka-ui/favicon/...`
- Verified proxied asset endpoints all return `200` with correct content types:
  - `/kafka-ui/assets/index-77be7e32.js` -> `application/javascript`
  - `/kafka-ui/assets/index-d9d582cd.css` -> `text/css`
  - `/kafka-ui/manifest.json` -> `application/json`
  - `/kafka-ui/favicon/favicon.ico` -> `image/x-icon`
- Kafka UI logs still show cluster connectivity after restart via `Metrics updated for cluster: federated-fraud-kafka`.
