#!/usr/bin/env bash
# =============================================================================
# PHASE 1 — Monorepo branch merger (AUTOMATED BY AI)
# =============================================================================
# Merges each service branch into a subdirectory of services/ using git subtree
# with a history-preserving fallback.
#
# Run from the ROOT of the repo (where .git lives).
# Pre-requisite: git remote "origin" is configured.
#
# Usage:
#   chmod +x scripts/phase1-merge-branches.sh
#   ./scripts/phase1-merge-branches.sh
# =============================================================================

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# ── Service map: branch → services/<dir> ──────────────────────────────────────
declare -A SERVICES=(
  [microservice-owner1-auth]="auth-service"
  [owner2_member_service]="member-service"
  [owner3_recruiter_service]="recruiter-service"
  [owner4_job_service]="job-service"
  [owner5_application_service]="application-service"
  [analytics-benchmarking]="analytics-service"
  [Owner8_Ai_Service]="ai-service"
)

# ── Port map (used only in README generation) ─────────────────────────────────
declare -A PORTS=(
  [auth-service]="8001"
  [member-service]="8002"
  [recruiter-service]="8003"
  [job-service]="8004"
  [application-service]="8005"
  [analytics-service]="8007"
  [ai-service]="8008"
)

mkdir -p services frontend

echo ""
echo "======================================================================"
echo " PHASE 1: Merging branches into monorepo"
echo "======================================================================"
echo ""

for branch in "${!SERVICES[@]}"; do
  dir="services/${SERVICES[$branch]}"
  echo "──────────────────────────────────────────────────────────────────"
  echo " Branch: $branch  →  $dir"
  echo "──────────────────────────────────────────────────────────────────"

  # Fetch branch if not already local
  git fetch origin "$branch:$branch" 2>/dev/null || git fetch origin "$branch" 2>/dev/null || {
    echo "[WARN] Could not fetch branch $branch — skipping"
    continue
  }

  if [ -d "$dir" ]; then
    echo "[SKIP] $dir already exists"
    continue
  fi

  # ── Strategy 1: git subtree (history-preserving) ────────────────────
  echo "[TRY] git subtree add --prefix=$dir $branch --squash"
  if git subtree add --prefix="$dir" "$branch" --squash 2>/dev/null; then
    echo "[OK ] git subtree succeeded for $branch"
  else
    # ── Strategy 2: copy fallback ────────────────────────────────────
    echo "[WARN] git subtree failed — using copy fallback"
    mkdir -p "$dir"
    git checkout "$branch" -- . 2>/dev/null || git checkout "origin/$branch" -- . 2>/dev/null || {
      echo "[ERR] Cannot checkout $branch"
      rmdir "$dir" 2>/dev/null || true
      continue
    }
    # Move all non-hidden root files into the service dir (skip .git, .DS_Store)
    find . -maxdepth 1 \
      ! -name '.' \
      ! -name '.git' \
      ! -name '.gitignore' \
      ! -name '.DS_Store' \
      ! -name 'services' \
      ! -name 'frontend' \
      ! -name 'scripts' \
      ! -name 'k8s' \
      ! -name '.github' \
      -exec git mv {} "$dir/" \; 2>/dev/null || \
      find . -maxdepth 1 \
        ! -name '.' ! -name '.git' ! -name '.gitignore' ! -name '.DS_Store' \
        ! -name 'services' ! -name 'frontend' ! -name 'scripts' \
        ! -name 'k8s' ! -name '.github' \
        -exec mv {} "$dir/" \;
    git add -A
    git commit -m "chore: move $branch → $dir (copy fallback)" || true
    echo "[OK ] Copy fallback done for $branch"
  fi
done

# ── Handle owner3 special case: code is nested inside services/recruiter-service ─
RECRUITER_DIR="services/recruiter-service"
if [ -d "$RECRUITER_DIR/services/recruiter-service" ]; then
  echo ""
  echo "[FIX] Flattening owner3 nested structure"
  mv "$RECRUITER_DIR/services/recruiter-service/"* "$RECRUITER_DIR/" 2>/dev/null || true
  rm -rf "$RECRUITER_DIR/services"
  git add -A && git commit -m "chore: flatten owner3 nested recruiter-service dir" || true
fi

# ── Handle owner8 special case: code is in services/ai-service ─────────────
AI_DIR="services/ai-service"
if [ -d "$AI_DIR/services/ai-service" ]; then
  echo ""
  echo "[FIX] Flattening owner8 nested ai-service structure"
  mv "$AI_DIR/services/ai-service/"* "$AI_DIR/" 2>/dev/null || true
  rm -rf "$AI_DIR/services"
  git add -A && git commit -m "chore: flatten owner8 nested ai-service dir" || true
fi

# ── Handle owner8 frontend ────────────────────────────────────────────────────
OWNER8_FRONTEND="$AI_DIR/frontend"
if [ -d "$OWNER8_FRONTEND" ] && [ ! -d "frontend/src" ]; then
  echo ""
  echo "[FIX] Moving owner8 frontend to /frontend"
  cp -r "$OWNER8_FRONTEND/"* frontend/ 2>/dev/null || true
  rm -rf "$OWNER8_FRONTEND"
  git add -A && git commit -m "chore: move owner8 frontend to root /frontend" || true
fi

echo ""
echo "======================================================================"
echo " Phase 1 complete. Run: tree services/ (or ls services/)"
echo "======================================================================"
