import pathlib
import shutil
import subprocess
import tempfile
import unittest

import jinja2


class SSHConfigTests(unittest.TestCase):
    def test_lan_is_direct_and_unreachable_lan_uses_cloudflare(self):
        template = jinja2.Template(
            pathlib.Path(__file__)
            .with_name("files")
            .joinpath("config.tera")
            .read_text()
        )
        for host, host_os in (("pod153", "darwin"), ("pod042", "linux"), ("", "linux")):
            rendered = template.render(
                vars={
                    "ssh_client_host": host,
                    "host_os": host_os,
                    "host_profile": host if host else "omarchy",
                }
            )
            rendered = "\n".join(
                line
                for line in rendered.splitlines()
                if not line.startswith("Include ")
            )
            targets = [("haos", "192.168.1.89", "22222", "haos-ssh.thurstons.house")]
            if host != "pod042":
                targets.append(
                    ("pod042", "10.10.10.42", "22", "pod042-ssh.thurstons.house")
                )
            for reachable in (True, False):
                predicate = shutil.which("true" if reachable else "false")
                assert predicate
                config = rendered.replace(
                    "~/.local/libexec/ssh-lan-reachable", predicate
                )
                with tempfile.NamedTemporaryFile(mode="w") as file:
                    file.write(config)
                    file.flush()
                    for alias, address, port, tunnel in targets:
                        with self.subTest(host=host, alias=alias, reachable=reachable):
                            output = subprocess.check_output(
                                ["ssh", "-G", "-F", file.name, alias],
                                text=True,
                                stderr=subprocess.PIPE,
                            )
                            options = dict(
                                line.split(" ", 1) for line in output.splitlines()
                            )
                            self.assertEqual(
                                options["hostname"], address if reachable else tunnel
                            )
                            self.assertEqual(options["port"], port)
                            self.assertEqual(options["hostkeyalias"], alias)
                            if reachable:
                                self.assertNotIn("proxycommand", options)
                            else:
                                self.assertEqual(
                                    options["proxycommand"],
                                    "cloudflared access ssh --hostname %h",
                                )


if __name__ == "__main__":
    unittest.main()
