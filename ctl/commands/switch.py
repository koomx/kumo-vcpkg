"""Switch to another vcpkg repository"""
import os
import subprocess
import sys


def setup(subparser):
    subparser.add_argument('dir', help='target vcpkg repository path')
    subparser.set_defaults(func=run)


def run(args):
    target = os.path.abspath(args.dir)
    vcpkgctl = os.path.join(target, 'vcpkgctl')
    if not os.path.isfile(vcpkgctl):
        print('error: {} is not a vcpkg repository (vcpkgctl not found)'.format(target), file=sys.stderr)
        sys.exit(1)
    subprocess.check_call([vcpkgctl, 'bootstrap'])
