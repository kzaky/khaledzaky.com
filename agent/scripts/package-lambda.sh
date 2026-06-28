#!/usr/bin/env bash
# Build ONE Lambda deployment artifact, with validation that makes a broken
# package impossible to produce.
#
# Usage: package-lambda.sh <function-dir> [output-zip]
#   <function-dir>  path to a Lambda dir containing index.py (e.g. chart)
#   [output-zip]    artifact path (default: <function-dir>.zip)
#
# The artifact is built from INSIDE the function dir so index.py lands at the
# zip root — Lambda's import requirement — and every source .py module under the
# dir (including subpackages such as chart/renderers/) is verified present before
# this script returns. An incomplete package is the cause of:
#
#     Runtime.ImportModuleError: No module named 'renderers'
#
# Shared code: if the function dir contains a `.common-deps` manifest (one module
# filename per line), each listed module is vendored from ../common/ into the zip
# ROOT (next to index.py) so it imports as a top-level module at runtime — e.g.
# `from llm import ...`. This keeps one source of truth in agent/common/ while
# preserving the self-contained-package invariant (no Lambda layer needed).
#
# This is the SINGLE SOURCE OF TRUTH for packaging. deploy.sh and
# deploy-lambda.sh both call it; nothing else should build a Lambda zip by hand.

set -euo pipefail

FN_DIR="${1:?Usage: package-lambda.sh <function-dir> [output-zip]}"
FN_DIR="${FN_DIR%/}"
FN_NAME="$(basename "$FN_DIR")"
OUT_ZIP="${2:-${FN_DIR}.zip}"

if [ ! -d "$FN_DIR" ]; then
  echo "!! package-lambda: directory not found: $FN_DIR" >&2
  exit 1
fi
if [ ! -f "$FN_DIR/index.py" ]; then
  echo "!! package-lambda: $FN_DIR/index.py not found — every Lambda needs an index.py handler" >&2
  exit 1
fi

# Source modules that must ship, minus caches. Shared by the compile and
# completeness checks so the two can never disagree about what's "in" the package.
# Note: mapfile requires bash 4+; macOS ships bash 3.x — use while-read instead.
SRC_MODULES=()
while IFS= read -r f; do
  SRC_MODULES+=("$f")
done < <(find "$FN_DIR" -name '*.py' -not -path '*/__pycache__/*' -not -path '*/.ruff_cache/*')

# Shared modules vendored from ../common per the function's .common-deps manifest.
# Each line is a plain filename under common/ (e.g. llm.py). The common dir is a
# sibling of the function dir, so dirname "$FN_DIR" resolves it for both the
# relative (deploy.sh: `draft`) and absolute (deploy-lambda.sh) invocations.
COMMON_DIR="$(dirname "$FN_DIR")/common"
COMMON_MODULES=()
if [ -f "$FN_DIR/.common-deps" ]; then
  while IFS= read -r mod; do
    mod="$(printf '%s' "$mod" | tr -d '[:space:]')"
    [ -z "$mod" ] && continue
    if [ ! -f "$COMMON_DIR/$mod" ]; then
      echo "!! package-lambda: .common-deps lists '$mod' but $COMMON_DIR/$mod does not exist" >&2
      exit 1
    fi
    COMMON_MODULES+=("$mod")
  done < "$FN_DIR/.common-deps"
fi

# 1) Syntax-check every source module — and every vendored common module —
#    (catches SyntaxError before it deploys).
for src in "${SRC_MODULES[@]}"; do
  if ! python3 -m py_compile "$src" 2>/tmp/pkg_pycompile_err; then
    echo "!! package-lambda: SYNTAX ERROR in $src" >&2
    cat /tmp/pkg_pycompile_err >&2
    exit 1
  fi
done
for mod in "${COMMON_MODULES[@]+"${COMMON_MODULES[@]}"}"; do
  if ! python3 -m py_compile "$COMMON_DIR/$mod" 2>/tmp/pkg_pycompile_err; then
    echo "!! package-lambda: SYNTAX ERROR in $COMMON_DIR/$mod" >&2
    cat /tmp/pkg_pycompile_err >&2
    exit 1
  fi
done

# 2) Build the zip from inside the dir; exclude caches for a lean, reproducible
#    artifact. Resolve the output to an absolute path first since we cd away.
mkdir -p "$(dirname "$OUT_ZIP")"
OUT_ABS="$(cd "$(dirname "$OUT_ZIP")" && pwd)/$(basename "$OUT_ZIP")"
rm -f "$OUT_ABS"
( cd "$FN_DIR" && zip -qr "$OUT_ABS" . -x '*__pycache__*' -x '*.ruff_cache*' -x '*.pyc' -x '.common-deps' )

# Vendor shared modules at the zip ROOT (next to index.py) so they import as
# top-level modules in Lambda, exactly as the tests load them.
for mod in "${COMMON_MODULES[@]+"${COMMON_MODULES[@]}"}"; do
  ( cd "$COMMON_DIR" && zip -q "$OUT_ABS" "$mod" )
done

zip_contents="$(unzip -l "$OUT_ABS" | awk '{print $4}')"

# 3) index.py must be at the zip root, not nested under <fn>/.
if ! printf '%s\n' "$zip_contents" | grep -qx 'index.py'; then
  echo "!! package-lambda: BAD ZIP — index.py not at root of ${OUT_ZIP} (nested path?)." >&2
  echo "   The artifact must be built from inside ${FN_DIR}/." >&2
  exit 1
fi

# 4) Every source module must be present. Catches a dropped subpackage (e.g.
#    chart/renderers) that imports fine from source but is absent from the zip —
#    which only surfaces at runtime as Runtime.ImportModuleError.
missing=""
for src in "${SRC_MODULES[@]}"; do
  rel="${src#"${FN_DIR}/"}"
  if ! printf '%s\n' "$zip_contents" | grep -qx "$rel"; then
    missing="${missing} ${rel}"
  fi
done
if [ -n "$missing" ]; then
  echo "!! package-lambda: INCOMPLETE PACKAGE — source modules missing from ${OUT_ZIP}:${missing}" >&2
  exit 1
fi

# 5) Every vendored common module must be present at the zip root. Catches a
#    .common-deps entry that silently failed to vendor (would surface at runtime
#    as Runtime.ImportModuleError: No module named 'llm').
for mod in "${COMMON_MODULES[@]}"; do
  if ! printf '%s\n' "$zip_contents" | grep -qx "$mod"; then
    echo "!! package-lambda: INCOMPLETE PACKAGE — vendored common module missing from ${OUT_ZIP}: ${mod}" >&2
    exit 1
  fi
done

echo "   Packaged ${FN_NAME} -> ${OUT_ZIP} (${#SRC_MODULES[@]} source + ${#COMMON_MODULES[@]} common modules)"
