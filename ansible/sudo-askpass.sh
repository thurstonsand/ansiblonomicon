#!/bin/bash
# Retrieves sudo password from 1Password
# Used by Ansible's become_password_file setting

op read "op://Private/Apple Macbook Login/password" 2>/dev/null
