#!/usr/bin/env bash
# One-command self-hosted Kubernetes deployment script
set -e

COLOR_GREEN='\033[0;32m'
COLOR_YELLOW='\033[1;33m'
COLOR_RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${COLOR_GREEN}[K8S]${NC} $1"; }
warn() { echo -e "${COLOR_YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${COLOR_RED}[ERROR]${NC} $1"; exit 1; }

# Check kubectl is available
command -v kubectl &> /dev/null || error "kubectl not found. Please install kubectl first."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

log "Building Docker images..."
docker build -t llm-logger-backend:latest "$ROOT_DIR/backend"
docker build -f "$ROOT_DIR/frontend/Dockerfile.prod" -t llm-logger-frontend:latest "$ROOT_DIR/frontend"

# If using kind, load images into cluster
if command -v kind &> /dev/null && kind get clusters 2>/dev/null | grep -q .; then
  log "Loading images into kind cluster..."
  kind load docker-image llm-logger-backend:latest
  kind load docker-image llm-logger-frontend:latest
fi

log "Applying Kubernetes manifests..."
kubectl apply -f "$SCRIPT_DIR/namespace.yaml"
kubectl apply -f "$SCRIPT_DIR/configmap.yaml"
kubectl apply -f "$SCRIPT_DIR/secret.yaml"
kubectl apply -f "$SCRIPT_DIR/postgres-pvc.yaml"
kubectl apply -f "$SCRIPT_DIR/postgres-deployment.yaml"
kubectl apply -f "$SCRIPT_DIR/postgres-service.yaml"

log "Waiting for PostgreSQL to be ready..."
kubectl rollout status deployment/postgres -n llm-logger --timeout=120s

kubectl apply -f "$SCRIPT_DIR/backend-deployment.yaml"
kubectl apply -f "$SCRIPT_DIR/backend-service.yaml"

log "Waiting for backend to be ready..."
kubectl rollout status deployment/backend -n llm-logger --timeout=120s

kubectl apply -f "$SCRIPT_DIR/frontend-deployment.yaml"
kubectl apply -f "$SCRIPT_DIR/frontend-service.yaml"
kubectl apply -f "$SCRIPT_DIR/ingress.yaml"

log "Waiting for frontend to be ready..."
kubectl rollout status deployment/frontend -n llm-logger --timeout=120s

log "✅ Deployment complete!"
echo ""
echo "Access the app:"
echo "  Via NodePort : http://$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[0].address}'):30000"
echo "  Via Ingress  : http://llm-logger.local (add to /etc/hosts)"
echo ""
echo "Useful commands:"
echo "  kubectl get pods -n llm-logger"
echo "  kubectl logs -n llm-logger deploy/backend"
echo "  kubectl logs -n llm-logger deploy/frontend"
