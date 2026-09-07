#!/usr/bin/env python3
"""Finish package-dependent container platform memberships."""

import grp
import pwd
import subprocess


def add_group(user: str, group: str) -> bool:
    account = pwd.getpwnam(user)
    target = grp.getgrnam(group)
    memberships = [entry.gr_name for entry in grp.getgrall() if user in entry.gr_mem]
    primary = grp.getgrgid(account.pw_gid).gr_name
    if group != primary and group not in memberships:
        subprocess.run(["usermod", "-aG", target.gr_name, user], check=True)
        return True
    return False


def remove_group(user: str, group: str) -> bool:
    pwd.getpwnam(user)
    target = grp.getgrnam(group)
    if user in target.gr_mem:
        subprocess.run(["gpasswd", "--delete", user, group], check=True)
        return True
    return False


def main() -> None:
    netdata_changed = remove_group("netdata", "docker")
    for required_user, required_groups in {
        "netdata": ("systemd-journal", "adm", "alerting"),
        "thurstonsand": ("docker", "media"),
    }.items():
        for required_group in required_groups:
            changed = add_group(required_user, required_group)
            netdata_changed |= required_user == "netdata" and changed
    if netdata_changed:
        subprocess.run(["systemctl", "restart", "netdata"], check=True)


if __name__ == "__main__":
    main()
