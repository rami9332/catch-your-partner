#!/bin/sh
set -eu

DIST_DIR="dist"
BACKEND_ORIGIN="${PUBLIC_BACKEND_ORIGIN:-}"

rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

cp index.html "$DIST_DIR/index.html"

cat > "$DIST_DIR/app-config.js" <<EOF
window.__CYP_RUNTIME_CONFIG__ = Object.assign({}, window.__CYP_RUNTIME_CONFIG__ || {}, {
  backendOrigin: ${BACKEND_ORIGIN:+\"$BACKEND_ORIGIN\"}${BACKEND_ORIGIN:-null}
});
EOF
