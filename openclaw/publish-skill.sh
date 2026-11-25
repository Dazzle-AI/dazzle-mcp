#!/usr/bin/env bash
#
# Package and publish a skill to ClawHub under the @Dazzle namespace.
#
# Usage (run from repo root; <skill-dir> resolves relative to this script's dir):
#   distribution/openclaw/publish-skill.sh <skill-dir>                    publish under @Dazzle (default)
#   distribution/openclaw/publish-skill.sh <skill-dir> --owner <h>        publish under a different handle
#   distribution/openclaw/publish-skill.sh <skill-dir> --version <semver> override version (else from SKILL.md frontmatter)
#   distribution/openclaw/publish-skill.sh <skill-dir> --dry-run          stage and validate, don't publish
#   distribution/openclaw/publish-skill.sh -h | --help                    show this help
#
# Version source: SKILL.md frontmatter `version:` field if present, otherwise the
# --version flag. ClawHub's `skill publish` requires --version, so one of those must
# be set. Only SKILL.md and README.md from the skill dir are bundled.

set -euo pipefail

# --- Args ---

SKILL_NAME=""
DRY_RUN=0
OWNER="Dazzle"
VERSION_OVERRIDE=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        --dry-run) DRY_RUN=1; shift ;;
        --owner) OWNER="$2"; shift 2 ;;
        --version) VERSION_OVERRIDE="$2"; shift 2 ;;
        -*) echo "unknown flag: $1" >&2; exit 2 ;;
        *)
            [[ -n "$SKILL_NAME" ]] && { echo "only one skill dir allowed (got '$SKILL_NAME' and '$1')" >&2; exit 2; }
            SKILL_NAME="$1"; shift
            ;;
    esac
done

[[ -n "$SKILL_NAME" ]] || { echo "missing skill dir. usage: $0 <skill-dir>" >&2; exit 2; }

# --- Locate skill dir ---

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$SCRIPT_DIR/$SKILL_NAME"
SKILL_MD="$SKILL_ROOT/SKILL.md"
README_MD="$SKILL_ROOT/README.md"

[[ -d "$SKILL_ROOT" ]] || { echo "skill dir not found: $SKILL_ROOT" >&2; exit 1; }
[[ -f "$SKILL_MD" ]]  || { echo "missing SKILL.md at $SKILL_MD" >&2; exit 1; }

# --- Preflight (only when actually publishing) ---

if [[ "$DRY_RUN" -eq 0 ]]; then
    if ! command -v clawhub >/dev/null 2>&1; then
        echo "clawhub CLI not installed. install per https://docs.openclaw.ai/" >&2
        exit 1
    fi
    if ! clawhub whoami >/dev/null 2>&1; then
        echo "not logged in to clawhub. run: clawhub login" >&2
        exit 1
    fi
fi

# --- Extract required fields from SKILL.md frontmatter ---

extract_field() {
    awk -v key="$1" '
        /^---$/ { in_fm = !in_fm; next }
        in_fm {
            if ($0 ~ "^"key":") {
                sub("^"key":[[:space:]]*", "")
                print
                exit
            }
        }
    ' "$SKILL_MD"
}

NAME="$(extract_field name)"
VERSION="${VERSION_OVERRIDE:-$(extract_field version)}"
DESCRIPTION="$(extract_field description)"

[[ -n "$NAME" ]]        || { echo "SKILL.md missing 'name' frontmatter" >&2; exit 1; }
[[ -n "$VERSION" ]]     || { echo "no version: not in SKILL.md frontmatter and --version flag not provided" >&2; exit 1; }
[[ -n "$DESCRIPTION" ]] || { echo "SKILL.md missing 'description' frontmatter" >&2; exit 1; }

SLUG="$(basename "$SKILL_ROOT")"
if [[ ! "$SLUG" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
    echo "skill folder name '$SLUG' is not a valid clawhub slug (^[a-z0-9][a-z0-9-]*\$)" >&2
    exit 1
fi

if [[ "$NAME" != "$SLUG" ]]; then
    echo "warning: SKILL.md 'name' ($NAME) differs from folder name ($SLUG); ClawHub will use the folder name as slug" >&2
fi

if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([-+].+)?$ ]]; then
    echo "version '$VERSION' is not valid semver" >&2
    exit 1
fi

# --- Stage clean bundle ---
# Stage inside a subdir named after the slug — ClawHub derives the published slug
# from the folder name, so a raw mktemp dir would publish under a `tmp-XXXXX` slug.
#
# Bundle policy:
#   - Always: SKILL.md
#   - If present: README.md, pyproject.toml, uv.lock
#   - LICENSE: copied from the shared distribution root
#   - If pyproject.toml is present (skill ships code), also bundle every top-level
#     subdir except dev/cache/scratch dirs in the denylist below.

STAGE_PARENT="$(mktemp -d)"
STAGE_DIR="$STAGE_PARENT/$SLUG"
mkdir -p "$STAGE_DIR"
trap 'rm -rf "$STAGE_PARENT"' EXIT

cp "$SKILL_MD" "$STAGE_DIR/SKILL.md"
for f in README.md pyproject.toml uv.lock; do
    [[ -f "$SKILL_ROOT/$f" ]] && cp "$SKILL_ROOT/$f" "$STAGE_DIR/$f"
done

# Shared LICENSE lives at the distribution root (one per published bundle).
# Required compliance artifact — fail rather than publish a license-less package.
SHARED_LICENSE="$SCRIPT_DIR/../LICENSE"
if [[ ! -f "$SHARED_LICENSE" ]]; then
    echo "shared LICENSE not found at $SHARED_LICENSE" >&2
    exit 1
fi
cp "$SHARED_LICENSE" "$STAGE_DIR/LICENSE"

if [[ -f "$SKILL_ROOT/pyproject.toml" ]]; then
    DENY=(tests scripts .venv .pytest_cache .ruff_cache .git __pycache__ dist build node_modules)
    for entry in "$SKILL_ROOT"/*/; do
        name="$(basename "$entry")"
        skip=0
        for d in "${DENY[@]}"; do
            [[ "$name" == "$d" ]] && { skip=1; break; }
        done
        [[ "$skip" -eq 1 ]] && continue
        cp -R "${entry%/}" "$STAGE_DIR/"
        find "$STAGE_DIR/$name" -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache \) -exec rm -rf {} + 2>/dev/null || true
    done
fi

DESC_PREVIEW="${DESCRIPTION:0:80}"
[[ ${#DESCRIPTION} -gt 80 ]] && DESC_PREVIEW="${DESC_PREVIEW}..."

echo "Staged bundle for ClawHub publish:"
echo "  publisher:   @${OWNER}"
echo "  slug:        ${SLUG}"
echo "  version:     ${VERSION}"
echo "  name:        ${NAME}"
echo "  description: ${DESC_PREVIEW}"
echo "  files:"
( cd "$STAGE_DIR" && find . -type f | sort | sed 's|^\./|    |' )

# --- Publish ---

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo
    echo "[dry-run] would run: clawhub skill publish <staged> --version ${VERSION} --owner ${OWNER}"
    exit 0
fi

echo
echo "Publishing @${OWNER}/${SLUG}@${VERSION} to ClawHub..."
clawhub skill publish "$STAGE_DIR" --version "$VERSION" --owner "$OWNER"
echo "Published @${OWNER}/${SLUG}@${VERSION}"
