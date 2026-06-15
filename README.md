# agentic-federated-cbdc-fraud-detection

## Recommended Local Kubernetes

Use `minikube` as the primary local Kubernetes environment for this repo.

Build the app images with one shared tag, then deploy with the helper scripts:

```bash
export IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d-%H%M%S)}"
minikube start -p minikube
kubectl config use-context minikube
bash scripts/build_all_images.sh --tag "${IMAGE_TAG}"
bash scripts/deploy_minikube.sh --tag "${IMAGE_TAG}" --profile minikube
```

This path builds the local images, loads them into `minikube`, and deploys the Helm release with the selected tag.

## Alternative Local Path

If you still need Docker Desktop, the repo also includes [scripts/deploy_docker_desktop.sh](scripts/deploy_docker_desktop.sh).

See [doc/DEPLOYMENT-GUIDE.md](doc/DEPLOYMENT-GUIDE.md) for the full build and deployment flow.
