#!/bin/sh
# usage: ./run_diff.sh <trace.csv> --level <name> [--attempt N]
cd "$(dirname "$0")" && exec python -I -c "import sys,runpy; sys.path.insert(0,'.'); sys.argv=['tracediff']+sys.argv[1:]; runpy.run_module('tools.tracediff', run_name='__main__')" "$@"
