# ============================================================
# deploy.ps1 — One-command Kubernetes deployment (Windows)
# Usage: .\k8s\deploy.ps1
# ============================================================
param(
    [string]$ClusterType = "kind",  # "kind" or "minikube"
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot
$K8S  = $PSScriptRoot

function Log   { Write-Host "[K8S] $args" -ForegroundColor Green }
function Warn  { Write-Host "[WARN] $args" -ForegroundColor Yellow }
function Error { Write-Host "[ERROR] $args" -ForegroundColor Red; exit 1 }

# ── Preflight checks ────────────────────────────────────────
Log "Checking prerequisites..."
if (-not (Get-Command kubectl -ErrorAction SilentlyContinue))  { Error "kubectl not found. Install from https://kubernetes.io/docs/tasks/tools/" }
if (-not (Get-Command docker  -ErrorAction SilentlyContinue))  { Error "docker not found. Install Docker Desktop." }

# ── Build Docker images ─────────────────────────────────────
if (-not $SkipBuild) {
    Log "Building backend image..."
    docker build -t llm-logger-backend:latest "$ROOT\backend"

    Log "Building frontend image (production nginx build)..."
    docker build -f "$ROOT\frontend\Dockerfile.prod" -t llm-logger-frontend:latest "$ROOT\frontend"
} else {
    Warn "Skipping image build (-SkipBuild flag set)"
}

# ── Load images into local cluster ──────────────────────────
if ($ClusterType -eq "kind") {
    if (-not (Get-Command kind -ErrorAction SilentlyContinue)) { Error "kind not found. Install from https://kind.sigs.k8s.io/" }
    Log "Loading images into kind cluster..."
    kind load docker-image llm-logger-backend:latest
    kind load docker-image llm-logger-frontend:latest
} elseif ($ClusterType -eq "minikube") {
    if (-not (Get-Command minikube -ErrorAction SilentlyContinue)) { Error "minikube not found." }
    Log "Loading images into minikube..."
    minikube image load llm-logger-backend:latest
    minikube image load llm-logger-frontend:latest
} else {
    Warn "Unknown cluster type '$ClusterType'. Assuming images are already available in the registry."
}

# ── Apply manifests in order ─────────────────────────────────
Log "Applying Kubernetes manifests..."

kubectl apply -f "$K8S\namespace.yaml"
kubectl apply -f "$K8S\configmap.yaml"
kubectl apply -f "$K8S\secret.yaml"

# PostgreSQL
kubectl apply -f "$K8S\postgres-pvc.yaml"
kubectl apply -f "$K8S\postgres-deployment.yaml"
kubectl apply -f "$K8S\postgres-service.yaml"

Log "Waiting for PostgreSQL to be ready (up to 2 min)..."
kubectl rollout status deployment/postgres -n llm-logger --timeout=120s

# Backend
kubectl apply -f "$K8S\backend-deployment.yaml"
kubectl apply -f "$K8S\backend-service.yaml"

Log "Waiting for backend to be ready (up to 2 min)..."
kubectl rollout status deployment/backend -n llm-logger --timeout=120s

# Frontend
kubectl apply -f "$K8S\frontend-deployment.yaml"
kubectl apply -f "$K8S\frontend-service.yaml"
kubectl apply -f "$K8S\ingress.yaml"

Log "Waiting for frontend to be ready (up to 1 min)..."
kubectl rollout status deployment/frontend -n llm-logger --timeout=60s

# ── Done ────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Deployment Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Pod status:" -ForegroundColor White
kubectl get pods -n llm-logger
Write-Host ""

$nodeIP = kubectl get nodes -o jsonpath='{.items[0].status.addresses[0].address}' 2>$null
Write-Host "Access the app:" -ForegroundColor White
Write-Host "  NodePort : http://${nodeIP}:30000" -ForegroundColor Green
Write-Host "  Ingress  : http://llm-logger.local  (add '$nodeIP llm-logger.local' to C:\Windows\System32\drivers\etc\hosts)" -ForegroundColor Green
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor White
Write-Host "  kubectl get pods -n llm-logger"
Write-Host "  kubectl logs -n llm-logger deploy/backend -f"
Write-Host "  kubectl logs -n llm-logger deploy/frontend"
Write-Host "  kubectl describe pod -n llm-logger <pod-name>"
Write-Host ""
Write-Host "To tear down: kubectl delete namespace llm-logger" -ForegroundColor Yellow
