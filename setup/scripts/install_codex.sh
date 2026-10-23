#!/usr/bin/env bash
# Install Codex CLI 0.162.1, the standalone build the pilot ran (x86_64-unknown-linux-musl), into CODEX_PACKAGE_DIR.
# The release archive and the codex binary are both checked against their sha256 (docs/ENVIRONMENT.md); CODEX_BIN must point
# into the package (host.example.env: ${CODEX_PACKAGE_DIR}/bin/codex), and its --version must be "codex-cli 0.162.1".
#   setup/scripts/install_codex.sh                 (host settings: FINAGENT_HOST_ENV, default setup/host.example.env)
set -euo pipefail
source "$(dirname "$0")/host_env.sh"

VERSION=0.162.1
TARGET=x86_64-unknown-linux-musl
ASSET="codex-package-$TARGET.tar.gz"
URL="https://github.com/openai/codex/releases/download/rust-v$VERSION/$ASSET"
ASSET_SHA256=a676f5722aae0d86cbe3764332f08eab1fdd89dc0a300b3ad4ffbf48611fa3e3
CODEX_SHA256=628e35487d888a28f0427fc37501da529dd3d81fcbad7a2c3421c1e8670d92e1

[[ "$(uname -sm)" == "Linux x86_64" ]] || { echo "the pinned build is for Linux x86_64 only" >&2; exit 1; }
dest="$CODEX_PACKAGE_DIR"
if [[ -f "$dest/bin/codex" ]] && echo "$CODEX_SHA256  $dest/bin/codex" | sha256sum --check --status; then
  echo "codex $VERSION is already in $dest"
else
  # replace only an empty folder or a Codex package (never an unrelated folder that a mis-set CODEX_PACKAGE_DIR names)
  if [[ -e "$dest" && ! -f "$dest/codex-package.json" && -n "$(ls -A "$dest" 2>/dev/null)" ]]; then
    echo "CODEX_PACKAGE_DIR=$dest exists and is not a Codex package; remove it or choose another path" >&2; exit 1
  fi
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  curl -fL --retry 3 -o "$tmp/$ASSET" "$URL"
  echo "$ASSET_SHA256  $tmp/$ASSET" | sha256sum --check
  mkdir "$tmp/pkg"
  tar -xzf "$tmp/$ASSET" -C "$tmp/pkg"
  echo "$CODEX_SHA256  $tmp/pkg/bin/codex" | sha256sum --check
  # as the release's install.sh does
  chmod 0755 "$tmp/pkg/bin/codex" "$tmp/pkg/bin/codex-code-mode-host" "$tmp/pkg/codex-path/rg"
  [[ ! -f "$tmp/pkg/codex-resources/bwrap" ]] || chmod 0755 "$tmp/pkg/codex-resources/bwrap"
  ln -sfn bin/codex "$tmp/pkg/codex"
  mkdir -p "$(dirname "$dest")"
  rm -rf "$dest"
  mv "$tmp/pkg" "$dest"
fi

case "$(readlink -f "$CODEX_BIN")" in
  "$(readlink -f "$dest")"/*) ;;
  *) echo "CODEX_BIN=$CODEX_BIN does not point into $dest; set CODEX_BIN=$dest/bin/codex in your host env file" >&2; exit 1 ;;
esac
version="$("$CODEX_BIN" --version)"
[[ "$version" == "codex-cli $VERSION" ]] || { echo "unexpected version: $version" >&2; exit 1; }
echo "$version at $CODEX_BIN"
