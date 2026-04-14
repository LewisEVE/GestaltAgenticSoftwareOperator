# Deployment Guide

## Docker Compose

From the repository root:

```bash
docker compose -f deployment/docker-compose.yml up --build
```

The local stack includes:

- `gestalt-core` FastAPI runtime
- Postgres with `pgvector`
- Redis 7
- Neo4j 5
- Prometheus
- Grafana
- OpenTelemetry Collector

### Default endpoints

- API: `http://localhost:8080`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`
- Neo4j Browser: `http://localhost:7474`

## Kubernetes manifests

Apply the application manifests in this order:

```bash
kubectl apply -f deployment/k8s/namespace.yaml
kubectl apply -f deployment/k8s/configmap.yaml
kubectl apply -f deployment/k8s/deployment.yaml
kubectl apply -f deployment/k8s/service.yaml
kubectl apply -f deployment/k8s/pdb.yaml
kubectl apply -f deployment/k8s/hpa.yaml
kubectl apply -f deployment/k8s/networkpolicy.yaml
kubectl apply -f deployment/k8s/servicemonitor.yaml
```

### Notes

- The provided Kubernetes manifests focus on the `gestalt-core` application pod.
- External dependencies such as Postgres, Redis, Neo4j, Prometheus, and Grafana can be managed
  either by platform services or their own charts/operators.
- Inject secrets such as `GESTALT_ADMIN_TOKEN`, database credentials, and provider keys using
  your platform secret manager.
