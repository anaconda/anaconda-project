#!/bin/bash
set -e

# be sure we are in the right place
test -e setup.py || exit 1
test -d anaconda_project || exit 1

(test -d build/packages && /bin/rm -r build/packages) || true
# python scripts/run_tests.py
python scripts/create_conda_packages.py

anaconda upload -u anaconda-platform --label dev build/packages/**/**/*.tar.bz2
