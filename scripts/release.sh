#!/usr/bin/env bash
# agentplane Release Script
# Usage: bash scripts/release.sh [status|promote-to-beta|promote-to-stable|rollback-stable|changelog]
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$REPO/.venv"; PYTHON="$VENV/bin/python"
cd "$REPO"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
_ok()      { echo -e "  ${GREEN}✓${NC}  $1"; }
_fail()    { echo -e "  ${RED}✗${NC}  $1"; exit 1; }
_warn()    { echo -e "  ${YELLOW}⚠${NC}  $1"; }
_section() { echo -e "\n${CYAN}${BOLD}━━━  $1  ━━━${NC}"; }
_info()    { echo -e "  ${CYAN}→${NC}  $1"; }

CURRENT_VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')

_run_regression() {
    _section "Running regression suite"
    bash "$REPO/scripts/regression.sh" && _ok "Regression passed" || _fail "Regression FAILED"
}

cmd_status() {
    echo -e "\n${CYAN}${BOLD}  agentplane Release Status${NC}"
    echo "  ─────────────────────────────────"
    for branch in master beta stable; do
        if git show-ref --quiet "refs/remotes/origin/$branch" 2>/dev/null || git show-ref --quiet "refs/heads/$branch" 2>/dev/null; then
            COMMIT=$(git log "origin/$branch" --oneline -1 2>/dev/null || git log "$branch" --oneline -1 2>/dev/null || echo "no commits")
            case "$branch" in master) ICON="🔧";; beta) ICON="🧪";; stable) ICON="🚀";; esac
            printf "  %s  %-8s  %s\n" "$ICON" "$branch" "$COMMIT"
        else
            printf "  ⬜  %-8s  (not found)\n" "$branch"
        fi
    done
    echo ""; echo "  Current version: $CURRENT_VERSION"
    echo "  PyPI: https://pypi.org/project/agentplane-py/"; echo ""
}

cmd_promote_to_beta() {
    _section "Promote master → beta  (v${CURRENT_VERSION})"
    BRANCH=$(git rev-parse --abbrev-ref HEAD)
    [[ "$BRANCH" != "master" && "$BRANCH" != "main" ]] && _fail "Must be on master/main"
    _run_regression
    git show-ref --quiet "refs/heads/beta" || git checkout -b beta && git checkout "$BRANCH"
    git checkout beta && git merge "$BRANCH" --no-edit -m "chore: promote $BRANCH → beta v${CURRENT_VERSION}"
    git tag "v${CURRENT_VERSION}-beta" -m "Beta v${CURRENT_VERSION}"
    git push origin beta --tags && _ok "beta pushed"
    git checkout "$BRANCH"
    echo ""; _ok "Promoted to beta: v${CURRENT_VERSION}"
}

cmd_promote_to_stable() {
    _section "Promote beta → stable + publish PyPI  (v${CURRENT_VERSION})"
    BRANCH=$(git rev-parse --abbrev-ref HEAD)
    _run_regression
    git show-ref --quiet "refs/heads/stable" || git checkout -b stable && git checkout "$BRANCH"
    git checkout stable && git merge "$BRANCH" --no-edit -m "chore: promote $BRANCH → stable v${CURRENT_VERSION}"
    STABLE_TAG="v${CURRENT_VERSION}"
    git tag -l | grep -q "^${STABLE_TAG}$" || git tag "$STABLE_TAG" -m "Release v${CURRENT_VERSION}"
    git push origin stable --tags && _ok "stable pushed"

    PYPI_TOKEN="${PYPI_TOKEN:-$(cat "$REPO/.pypi-token" 2>/dev/null || echo "")}"
    if [ -z "$PYPI_TOKEN" ]; then
        _warn "No PyPI token. Run: PYPI_TOKEN=<tok> bash scripts/release.sh promote-to-stable"
    else
        "$PYTHON" -m build -q && _ok "Built dist/"
        TWINE_USERNAME="__token__" TWINE_PASSWORD="$PYPI_TOKEN" \
            "$PYTHON" -m twine upload "dist/agentplane_py-${CURRENT_VERSION}"* | grep -E "Uploading|View at|ERROR" || true
        _ok "Published agentplane-py v${CURRENT_VERSION}"
    fi
    git checkout "$BRANCH"
    echo ""; _ok "━━━ RELEASE COMPLETE: agentplane-py v${CURRENT_VERSION} ━━━"
}

cmd_changelog() {
    LAST=$(git tag --sort=-version:refname | grep -v beta | grep -v rc | head -1 || echo "")
    [ -z "$LAST" ] && git log --oneline || { _section "Changes since $LAST"; git log "${LAST}..HEAD" --oneline; }
}

CMD="${1:-status}"
case "$CMD" in
    status)            cmd_status ;;
    promote-to-beta)   cmd_promote_to_beta ;;
    promote-to-stable) cmd_promote_to_stable ;;
    changelog)         cmd_changelog ;;
    *) echo "Usage: $0 [status|promote-to-beta|promote-to-stable|changelog]"; exit 1 ;;
esac
