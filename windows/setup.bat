@echo off
setlocal
set "PROJECT_ROOT=%~dp0.."
set "PYTHON_SPEC="
py -3.13 -c "import sys" >nul 2>&1 && set "PYTHON_SPEC=-3.13"
if not defined PYTHON_SPEC py -3.12 -c "import sys" >nul 2>&1 && set "PYTHON_SPEC=-3.12"
if not defined PYTHON_SPEC py -3.11 -c "import sys" >nul 2>&1 && set "PYTHON_SPEC=-3.11"
if not defined PYTHON_SPEC (
  echo Need Python 3.11, 3.12, or 3.13.
  exit /b 1
)
py %PYTHON_SPEC% -m venv "%PROJECT_ROOT%\.venv-supported" || exit /b 1
"%PROJECT_ROOT%\.venv-supported\Scripts\python.exe" -m pip install --upgrade pip || exit /b 1
"%PROJECT_ROOT%\.venv-supported\Scripts\python.exe" -m pip install -e "%PROJECT_ROOT%[dataset]" || exit /b 1
"%PROJECT_ROOT%\.venv-supported\Scripts\python.exe" -m unittest discover -s "%PROJECT_ROOT%\tests" || exit /b 1
