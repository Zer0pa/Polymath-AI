#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${ROOT_DIR}/bin"
mkdir -p "${OUT_DIR}"

clang++ -std=c++17 -O3 -Wall -Wextra -Werror \
  "${ROOT_DIR}/phase4_bridge_cell_runner.cpp" \
  -ldl \
  -o "${OUT_DIR}/phase4_bridge_cell_runner"

echo "${OUT_DIR}/phase4_bridge_cell_runner"
