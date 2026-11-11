#!/bin/sh
set -eu

# Render the site config from the template, substituting BACKEND_HOST.
#
# The official nginx image runs every executable in /docker-entrypoint.d
# before launching nginx, so we render the runtime config there.

TEMPLATE=/etc/nginx/conf.d/site.conf.template
TARGET=/etc/nginx/conf.d/site.conf

# When the build copied site.conf directly (no template), keep going.
if [ -f "$TEMPLATE" ]; then
  envsubst '$BACKEND_HOST' < "$TEMPLATE" > "$TARGET"
fi
