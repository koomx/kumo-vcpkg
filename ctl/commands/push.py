"""Push registry changes to remote"""
import subprocess
import sys

import util


def setup(subparser):
    subparser.set_defaults(func=run)


def run(args):
    root = util.vcpkg_root()
    result = subprocess.run(['git', 'push'], cwd=root)
    sys.exit(result.returncode)
