"""Just the scrub part: pyinfra inventory.py parts/scrub.py

The `--tags scrub` analog. It runs standalone because zfs_maintenance's data
defaults include alerting's, so alerting_bin_dir and alerting_state_dir are in
scope without alerting itself running.
"""

from bunker.zfs_maintenance import scrub

scrub()
