#!/usr/bin/env bash
# The weights of one local model: its Hugging Face repository at the revision in setup/models.toml, into MODEL_DIR/<weights>,
# then every file checked against the manifest named by models.toml's weights_sha256 (setup/weights/<model>.sha256).
#   setup/scripts/download_weights.sh qwen3_8b|qwen35_9b|qwen38_27b      (REVISION=<commit> overrides models.toml's hf_revision)
set -euo pipefail
source "$(dirname "$0")/host_env.sh"

key="${1:?usage: download_weights.sh <model key>}"
read -r repo revision weights manifest < <("${PYTHON:-python3.12}" - "$REPO_ROOT/setup/models.toml" "$key" <<'PY'
import sys, tomllib
m = tomllib.load(open(sys.argv[1], "rb"))[sys.argv[2]]["vllm"]
print(m["hf_repo"], m["hf_revision"], m["weights"], m["weights_sha256"])
PY
)
revision="${REVISION:-$revision}"
[[ "$revision" =~ ^[0-9a-f]{40}$ ]] || { echo "$key: hf_revision '$revision' is not a commit; pass REVISION=<commit>" >&2; exit 1; }
manifest="$REPO_ROOT/$manifest"
target="$MODEL_DIR/$weights"

"$VLLM_ENV/bin/hf" download "$repo" --revision "$revision" --local-dir "$target"
(cd "$target" && sha256sum --check --quiet "$manifest")
echo "$repo@$revision in $target: all $(wc -l < "$manifest") files match $manifest"
