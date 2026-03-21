#!/bin/sh
set -eu

DIST_DIR="dist"
BACKEND_ORIGIN="${PUBLIC_BACKEND_ORIGIN:-}"

rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

cp index.html "$DIST_DIR/index.html"

BACKEND_JSON="null"
if [ -n "$BACKEND_ORIGIN" ]; then
  ESCAPED_BACKEND=$(printf '%s' "$BACKEND_ORIGIN" | sed 's/\\/\\\\/g; s/"/\\"/g')
  BACKEND_JSON="\"$ESCAPED_BACKEND\""
fi

cat > "$DIST_DIR/app-config.js" <<EOF
window.__CYP_RUNTIME_CONFIG__ = Object.assign({}, window.__CYP_RUNTIME_CONFIG__ || {}, {
  backendOrigin: $BACKEND_JSON
});
EOF
