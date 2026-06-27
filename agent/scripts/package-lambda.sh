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
mapfile -t SRC_MODULES < <(find "$FN_DIR" -name '*.py' -not -path '*/__pycache__/*' -not -path '*/.ruff_cache/*')

# 1) Syntax-check every source module (catches SyntaxError before it deploys).
for src in "${SRC_MODULES[@]}"; do
  if ! python3 -m py_compile "$src" 2>/tmp/pkg_pycompile_err; then
    echo "!! package-lambda: SYNTAX ERROR in $src" >&2
    cat /tmp/pkg_pycompile_err >&2
    exit 1
  fi
done

# 2) Build the zip from inside the dir; exclude caches for a lean, reproducible
#    artifact. Resolve the output to an absolute path first since we cd away.
mkdir -p "$(dirname "$OUT_ZIP")"
OUT_ABS="$(cd "$(dirname "$OUT_ZIP")" && pwd)/$(basename "$OUT_ZIP")"
rm -f "$OUT_ABS"
( cd "$FN_DIR" && zip -qr "$OUT_ABS" . -x '*__pycache__*' -x '*.ruff_cache*' -x '*.pyc' )

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

echo "   Packaged ${FN_NAME} -> ${OUT_ZIP} (${#SRC_MODULES[@]} Python modules)"
