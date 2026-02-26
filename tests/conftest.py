import sys
import os

_tests_dir = os.path.dirname(__file__)

# Add fetchers/ to the import path so tests can import modules directly
sys.path.insert(0, os.path.join(_tests_dir, '..', 'fetchers'))
# Add tests/ itself so helpers.py can be imported
sys.path.insert(0, _tests_dir)
