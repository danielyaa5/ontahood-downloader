#!/usr/bin/env bash
set -euo pipefail
# pre-commit.sh v3.1 — 2025-09-30
# - Universal2 build (x86_64 + arm64)
# - Bundles everything in requirements.txt
# - Safe handling for empty arrays under `set -u` on macOS Bash 3.2

# ---------- CONFIG ----------
APP_NAME="Ontahood Downloader"
APP_DIR="dist/${APP_NAME}.app"
APP_BIN="${APP_DIR}/Contents/MacOS/${APP_NAME}"
APP_ZIP="${APP_NAME}.app.zip"                 # zip will be created at repo root
README="README.md"
README_EXPECT_LINK='Ontahood%20Downloader.app.zip'
MAX_SIZE=$((95 * 1024 * 1024))                # 95MB threshold
PYTHON_UNI="/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
REQ_FILE="requirements.txt"
# -----------------------------

red()   { printf "\033[31m%s\033[0m\n" "$*" >&2; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
yellow(){ printf "\033[33m%s\033[0m\n" "$*"; }

# Collect staged files (safe with -u even if none are staged)
STAGED=()
while IFS= read -r -d '' f; do STAGED+=("$f"); done < <(git diff --cached --name-only -z || printf '\0')

# 1) Block secrets
for f in "${STAGED[@]-}"; do
  case "$f" in
    credentials.json|token.json)
      red "✖ Refusing to commit $f (Google OAuth secrets)."
      red "  Remove from index:  git restore --staged $f"
      exit 1;;
  esac
done

# 2) Block raw .app/.dmg
for f in "${STAGED[@]-}"; do
  case "$f" in
    dmg-staging/*) continue ;;
    *.app|*.app/*|*.dmg)
      red "✖ Refusing to commit macOS bundles/images: $f"
      exit 1;;
  esac
done

# 3) Large file guard
for f in "${STAGED[@]-}"; do
  [[ -f "$f" ]] || continue
  size=$(stat -f "%z" "$f" 2>/dev/null || echo 0)
  if (( size > MAX_SIZE )); then
    if [[ "${GIT_ALLOW_BIG:-0}" != "1" ]]; then
      mb=$(printf "%.1f" "$(echo "$size / 1048576" | bc -l)")
      red "✖ '$f' is ${mb} MB (>95MB). GitHub rejects >100MB."
      exit 1
    else
      yellow "⚠ Allowing large file '$f' due to GIT_ALLOW_BIG=1"
    fi
  fi
done

# 4) README link check (warn-only)
if [[ -f "$README" ]] && ! LC_ALL=C grep -q "$README_EXPECT_LINK" "$README"; then
  yellow "⚠ README missing expected link: $README_EXPECT_LINK"
fi

# -------- Build & zip --------
echo "[pre-commit] Building app with PyInstaller (universal2)…"
rm -rf build dist

# Ensure tooling
"$PYTHON_UNI" -m pip install --quiet --upgrade pip wheel setuptools pyinstaller

# Load requirements, normalize names (drop version pins/extras)
REQ_PKGS=()
if [[ -f "$REQ_FILE" ]]; then
  while IFS= read -r raw; do
    # skip blanks/comments
    [[ -z "${raw// }" || "$raw" == \#* ]] && continue

    # cut off version/markers/extras: requests[socks]>=2.0; python_version<"3.13"
    base="$raw"
    base="${base%%;*}"   # remove env markers
    base="${base%%==*}"  # remove exact pins
    base="${base%%>=*}"  # remove version pins
    base="${base%%<=*}"
    base="${base%%>*}"
    base="${base%%<*}"
    base="${base%%=*}"
    base="${base%%[*}"   # remove extras like requests[socks]

    base="$(echo "$base" | tr -d ' ')"  # strip spaces
    [[ -n "$base" ]] && REQ_PKGS+=("$base")
  done < "$REQ_FILE"
fi

# Deduplicate
REQ_PKGS=($(printf "%s\n" "${REQ_PKGS[@]}" | sort -u))
# Ensure all requirements are installed in $PYTHON_UNI (both arch slices)
for pkg in "${REQ_PKGS[@]-}"; do
  if ! "$PYTHON_UNI" -m pip show "$pkg" >/dev/null 2>&1; then
    yellow "⚠ Installing missing package into $PYTHON_UNI: $pkg"
    "$PYTHON_UNI" -m pip install "$pkg"
  fi
done

# Build hidden-import/collect-all flags from requirements
REQ_IMPORT_FLAGS=()
for pkg in "${REQ_PKGS[@]-}"; do
  REQ_IMPORT_FLAGS+=( --hidden-import "$pkg" --collect-all "$pkg" )
done

# Extra safety for packages that are commonly missed by analysis
EXTRA_FLAGS=(
  --hidden-import requests --collect-all requests
)

ADD_DATA=( --add-data "drive_fetch_resilient.py:." )
[[ -f credentials.json ]] && ADD_DATA+=( --add-data "credentials.json:." )

"$PYTHON_UNI" -m PyInstaller \
  --name "$APP_NAME" \
  --windowed \
  --noconfirm \
  --target-architecture universal2 \
  "${EXTRA_FLAGS[@]}" \
  "${REQ_IMPORT_FLAGS[@]-}" \
  "${ADD_DATA[@]}" \
  gui_main.py

# -------- Post-build verification --------
if [[ ! -x "$APP_BIN" ]]; then
  red "✖ Built app binary not found or not executable: $APP_BIN"
  exit 1
fi

echo "[pre-commit] Verifying universal2 slices…"
BIN_ARCHS=$(lipo -archs "$APP_BIN" 2>/dev/null || true)
if [[ "$BIN_ARCHS" != *x86_64* || "$BIN_ARCHS" != *arm64* ]]; then
  red "✖ App binary is not universal2. Found: $BIN_ARCHS"
  exit 1
fi

PY_PATH="$APP_DIR/Contents/Frameworks/Python.framework/Versions/3.13/Python"
if [[ ! -f "$PY_PATH" ]]; then
  red "✖ Embedded Python not found at $PY_PATH"
  exit 1
fi
PY_ARCHS=$(lipo -archs "$PY_PATH" 2>/dev/null || true)
if [[ "$PY_ARCHS" != *x86_64* || "$PY_ARCHS" != *arm64* ]]; then
  red "✖ Embedded Python is not universal2. Found: $PY_ARCHS"
  exit 1
fi

green "✓ Universal2 verification passed (bin: $BIN_ARCHS, python: $PY_ARCHS)"

# -------- Zip the .app for release --------
echo "[pre-commit] Rebuilding ${APP_ZIP}…"
if [[ -d "$APP_DIR" ]]; then
  ( cd dist && ditto -c -k --sequesterRsrc --keepParent "${APP_NAME}.app" "../${APP_ZIP}" )
  git add "${APP_ZIP}"
  green "✓ Staged ${APP_ZIP}"
else
  yellow "⚠ ${APP_DIR} not found; skipping zip."
fi

green "✓ pre-commit checks passed"