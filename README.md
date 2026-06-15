# agentic-federated-cbdc-fraud-detection

## Recommended Local Kubernetes

Use `minikube` as the primary local Kubernetes environment for this repo.

Build the app images with one shared tag, then deploy with the helper scripts:

```bash
export IMAGE_TAG=latest
minikube start -p minikube --driver=docker --container-runtime=containerd --cpus=4 --memory=8192 --disk-size=40g
kubectl config use-context minikube
bash scripts/build_all_images.sh --tag "${IMAGE_TAG}"
bash scripts/deploy_minikube.sh --tag "${IMAGE_TAG}" --profile minikube
```

This path builds the local images, loads them into `minikube`, and deploys the Helm release with the selected tag.

To open the dashboard after deployment:

```bash
kubectl port-forward svc/fraud-dashboard 3000:3000
```

Then browse to `http://127.0.0.1:3000`.

The dashboard now proxies its own upstream API and WebSocket requests, so you do not need separate localhost port-forwards for `local-agent`, `transaction-graph`, or `alerting` just to use the UI.

## Alternative Local Path

If you still need Docker Desktop, the repo also includes [scripts/deploy_docker_desktop.sh](scripts/deploy_docker_desktop.sh).

See [doc/DEPLOYMENT-GUIDE.md](doc/DEPLOYMENT-GUIDE.md) for the full build and deployment flow.
