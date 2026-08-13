"""Sync local registry with remote (git pull)"""
import subprocess
import sys

import util

COMMAND_NAME = 'pull'


def setup(subparser):
    subparser.set_defaults(func=run)


def run(args):
    root = util.vcpkg_root()
    result = subprocess.run(['git', 'pull'], cwd=root)
    sys.exit(result.returncode)
