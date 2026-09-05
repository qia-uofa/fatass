#!/usr/bin/env bash
# Uninstall (if present) and reinstall the fatass VS Code extension from a
# fresh build. Safe to run on a machine that's never had `npm install` run
# here yet -- installs deps first if node_modules is missing, and falls
# back to a common Windows nodejs install location if `node`/`npm` aren't
# already on PATH.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

if ! command -v npm >/dev/null 2>&1; then
    for candidate in "/c/Program Files/nodejs" "/c/Program Files (x86)/nodejs"; do
        if [ -x "$candidate/npm.cmd" ] || [ -x "$candidate/npm" ]; then
            export PATH="$candidate:$PATH"
            break
        fi
    done
fi

if ! command -v npm >/dev/null 2>&1; then
    echo "error: npm not found on PATH or in common install locations. Install Node.js first." >&2
    exit 1
fi

if ! command -v code >/dev/null 2>&1; then
    echo "error: 'code' CLI not found on PATH. Install VS Code and run 'Shell Command: Install code command in PATH'." >&2
    exit 1
fi

if [ ! -d node_modules ]; then
    echo "== installing dependencies (first run) =="
    npm install
fi

echo "== compiling =="
npm run compile

echo "== packaging =="
npx vsce package

EXT_ID=$(node -p "const p=require('./package.json'); (p.publisher || 'undefined_publisher') + '.' + p.name")
VSIX=$(ls -t fatass-vscode-*.vsix | head -n1)

if code --list-extensions | grep -qx "$EXT_ID"; then
    echo "== uninstalling existing $EXT_ID =="
    code --uninstall-extension "$EXT_ID"
else
    echo "== $EXT_ID not currently installed, skipping uninstall =="
fi

echo "== installing $VSIX =="
code --install-extension "$VSIX"

echo "== done -- reload the VS Code window to pick up the new build =="
