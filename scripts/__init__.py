# Makes `scripts` an explicit package so mypy cannot map the same file under
# two module names (`seed_data_part1` and `scripts.seed_data_part1`). The
# duplicate-module error only appears when mypy scans the whole tree; CI runs
# `mypy main.py database.py` and never hit it, but `mypy .` locally did.
