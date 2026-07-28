#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN=""
for candidate in python3.13 python3.12 python3.11; do
  if command -v "${candidate}" >/dev/null 2>&1; then
    PYTHON_BIN="${candidate}"
    break
  fi
done
if [[ -z "${PYTHON_BIN}" ]]; then
  echo "需要 Python 3.11、3.12 或 3.13。" >&2
  exit 1
fi
"${PYTHON_BIN}" -m venv "${PROJECT_ROOT}/.venv-supported"
"${PROJECT_ROOT}/.venv-supported/bin/python" -m pip install --upgrade pip
"${PROJECT_ROOT}/.venv-supported/bin/python" -m pip install -e "${PROJECT_ROOT}[dataset]"
"${PROJECT_ROOT}/.venv-supported/bin/python" -m unittest discover -s "${PROJECT_ROOT}/tests"
