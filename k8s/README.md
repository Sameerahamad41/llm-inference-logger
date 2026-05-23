# Kubernetes Deployment Guide

## Architecture in K8s

```
                    ┌─────────────────────────────────┐
       Browser      │     Kubernetes Cluster           │
          │         │                                  │
          ▼         │  ┌──────────┐   ┌────────────┐  │
    NodePort:30000  │  │ Frontend │──▶│  Backend   │  │
    (or Ingress)    │  │ (nginx)  │   │ (FastAPI)  │  │
                    │  └──────────┘   └─────┬──────┘  │
                    │                       │         │
                    │                 ┌─────▼──────┐  │
                    │                 │ PostgreSQL │  │
                    │                 │    + PVC   │  │
                    │                 └────────────┘  │
                    └─────────────────────────────────┘
```

## Namespace: `llm-logger`

All resources are isolated in the `llm-logger` namespace.

---

## Prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| Docker Desktop | Build images | [docker.com](https://www.docker.com/products/docker-desktop/) |
| kubectl | K8s CLI | [kubernetes.io](https://kubernetes.io/docs/tasks/tools/) |
| kind **or** minikube | Local K8s cluster | [kind.sigs.k8s.io](https://kind.sigs.k8s.io/) |

---

## Quick Start (Windows)

### Step 1 — Create a local cluster

**Option A: kind (recommended)**
```powershell
# Install kind
choco install kind   # or: winget install Kubernetes.kind

# Create cluster
kind create cluster --name llm-logger
```

**Option B: minikube**
```powershell
minikube start --driver=docker
```

### Step 2 — Add your API key to the secret

Edit [`k8s/secret.yaml`](secret.yaml) and replace the placeholder:
```yaml
stringData:
  GROQ_API_KEY: "gsk_your_actual_key_here"  # ← put your key here
```

### Step 3 — Run the deploy script

```powershell
# From the project root:
.\k8s\deploy.ps1

# Or for minikube:
.\k8s\deploy.ps1 -ClusterType minikube
```

This single command will:
1. ✅ Build Docker images (`backend` + `frontend`)
2. ✅ Load them into the local cluster
3. ✅ Apply all manifests in dependency order
4. ✅ Wait for each pod to be healthy
5. ✅ Print access URLs

### Step 4 — Access the app

```
http://<node-ip>:30000          ← via NodePort (always works)
http://llm-logger.local         ← via Ingress (requires hosts entry)
```

To use the Ingress hostname, add this line to `C:\Windows\System32\drivers\etc\hosts`:
```
127.0.0.1   llm-logger.local
```

---

## File Structure

```
k8s/
├── namespace.yaml            # llm-logger namespace
├── configmap.yaml            # Non-sensitive env vars
├── secret.yaml               # API keys (edit before deploying!)
├── postgres-pvc.yaml         # 2Gi persistent volume for DB
├── postgres-deployment.yaml  # PostgreSQL 16
├── postgres-service.yaml     # Internal ClusterIP service
├── backend-deployment.yaml   # FastAPI backend (with init container)
├── backend-service.yaml      # Internal ClusterIP service
├── frontend-deployment.yaml  # nginx serving React build
├── frontend-service.yaml     # NodePort :30000
├── ingress.yaml              # Ingress for llm-logger.local
├── deploy.ps1                # Windows one-command deploy
└── deploy.sh                 # Linux/Mac one-command deploy
```

---

## Useful Commands

```powershell
# View all pods
kubectl get pods -n llm-logger

# View all services
kubectl get svc -n llm-logger

# Watch pod startup in real-time
kubectl get pods -n llm-logger -w

# Stream backend logs
kubectl logs -n llm-logger deploy/backend -f

# Stream frontend logs
kubectl logs -n llm-logger deploy/frontend

# Describe a pod (for debugging CrashLoopBackOff etc.)
kubectl describe pod -n llm-logger <pod-name>

# Open a shell inside the backend pod
kubectl exec -it -n llm-logger deploy/backend -- /bin/bash

# Port-forward backend directly (bypass nginx)
kubectl port-forward -n llm-logger svc/backend 8000:8000
```

---

## Updating After Code Changes

```powershell
# Rebuild images
docker build -t llm-logger-backend:latest ./backend
docker build -f ./frontend/Dockerfile.prod -t llm-logger-frontend:latest ./frontend

# Reload into kind
kind load docker-image llm-logger-backend:latest
kind load docker-image llm-logger-frontend:latest

# Restart deployments to pick up new images
kubectl rollout restart deployment/backend -n llm-logger
kubectl rollout restart deployment/frontend -n llm-logger
```

---

## Tear Down

```powershell
# Delete everything (namespace + all resources inside it)
kubectl delete namespace llm-logger

# Or delete just the cluster
kind delete cluster --name llm-logger
```

---

## Troubleshooting

| Problem | Solution |
|---------|---------|
| Pod stuck in `Pending` | Check PVC: `kubectl describe pvc -n llm-logger` — may need a StorageClass |
| `ImagePullBackOff` | Image wasn't loaded: `kind load docker-image llm-logger-backend:latest` |
| `CrashLoopBackOff` backend | Check logs: `kubectl logs -n llm-logger deploy/backend` |
| Can't reach NodePort | Use `kubectl port-forward svc/frontend 3000:80 -n llm-logger` |
| DB connection error | Ensure postgres pod is `Running` before backend starts |
