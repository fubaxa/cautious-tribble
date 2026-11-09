#!/bin/sh
# usage: ./run.sh <module> [args]   e.g. ./run.sh converter.convert --local test
cd "$(dirname "$0")" && m="$1" && shift && exec python -I -c "import sys,runpy; sys.path.insert(0,'.'); m=sys.argv[1]; sys.argv=[m]+sys.argv[2:]; runpy.run_module(m, run_name='__main__')" "$m" "$@"
