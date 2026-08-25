# The Bunker configures itself from its own checkout, so the target is the
# machine pyinfra runs on. Ansible's equivalent is inventory/targets/pod042.yml
# with ansible_connection: local.
pod042 = ["@local"]
