"""Show latest registry git log"""
import subprocess
import sys

import util


def setup(subparser):
    subparser.add_argument('-n', type=int, default=10,
                           help='number of commits (default: 10)')
    subparser.set_defaults(func=run)


def run(args):
    root = util.vcpkg_root()
    result = subprocess.run(
        ['git', 'log', '--oneline', '-{}'.format(args.n)],
        cwd=root
    )
    sys.exit(result.returncode)
