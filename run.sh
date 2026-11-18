#!/bin/sh
# usage: ./run.sh <module> [args]   e.g. ./run.sh converter.convert --local test
# Uses PyPy when it's unzipped at %LOCALAPPDATA%/pypy-download (3x faster on traces, same results);
# PY=python ./run.sh ... forces CPython.
pypy="$LOCALAPPDATA/pypy-download/pypy3.12-v8.0.1-win64/pypy3.exe"
if [ -z "$PY" ]; then if [ -x "$pypy" ]; then PY="$pypy"; else PY=python; fi; fi
cd "$(dirname "$0")" && m="$1" && shift && exec "$PY" -I -c "import sys,runpy; sys.path.insert(0,'.'); m=sys.argv[1]; sys.argv=[m]+sys.argv[2:]; runpy.run_module(m, run_name='__main__')" "$m" "$@"
