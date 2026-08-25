"""The whole segment: alerting + zfs_maintenance.

pyinfra inventory.py deploy.py
"""

from bunker.alerting import alerting
from bunker.zfs_maintenance import zfs_maintenance

alerting()
zfs_maintenance()
