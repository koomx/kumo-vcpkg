"""Upgrade vcpkgctl and vcpkg binary to latest version"""
import os
import shutil
import subprocess
import sys
import tempfile

import util
from bootstrap.detect import detect_platform
from bootstrap.download import download_binary
from bootstrap.install import install_binary

_REMOTE_URL = 'https://github.com/koomx/kumo-vcpkg.git'
_CTL_FILES = ['vcpkgctl', 'vcpkgctl.bat']


def setup(subparser):
    subparser.add_argument(
        '--force', action='store_true',
        help='perform the upgrade (default: dry-run only)'
    )
    subparser.set_defaults(func=run)


def run(args):
    root = util.vcpkg_root()
    tmpdir = tempfile.mkdtemp(prefix='vcpkgctl-upgrade-')

    try:
        _check_upgrade(root, tmpdir, args.force)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _check_upgrade(root, tmpdir, force):
    print('checking remote repository...')
    subprocess.run(
        ['git', 'clone', '--depth', '1', _REMOTE_URL, tmpdir],
        check=True, capture_output=True
    )

    local_ver = _read_version(root)
    remote_ver = _read_version(tmpdir)

    _show_version('vcpkgctl (local)', local_ver)
    _show_version('vcpkgctl (remote)', remote_ver)

    _print_binary_version(root, 'vcpkg binary (local)')

    same = local_ver == remote_ver
    if same and not force:
        print()
        print('already up to date')
        return

    print()
    if not force:
        print('dry-run: remote version differs, run with --force to upgrade')
        return

    _apply_upgrade(root, tmpdir)


def _apply_upgrade(root, tmpdir):
    print()
    print('upgrading vcpkgctl...')
    for name in _CTL_FILES:
        src = os.path.join(tmpdir, name)
        dst = os.path.join(root, name)
        if os.path.isfile(src):
            shutil.copy2(src, dst)

    ctl_src = os.path.join(tmpdir, 'ctl')
    ctl_dst = os.path.join(root, 'ctl')
    if os.path.isdir(ctl_src):
        if os.path.isdir(ctl_dst):
            shutil.rmtree(ctl_dst)
        shutil.copytree(ctl_src, ctl_dst)
    print('vcpkgctl updated')

    print()
    print('upgrading vcpkg binary...')
    plat = detect_platform()
    dl_path = download_binary(plat)
    install_binary(dl_path, root)
    print('vcpkg binary updated')

    print()
    print('upgrade complete')


def _read_version(base_dir):
    path = os.path.join(base_dir, 'ctl', 'VERSION')
    if os.path.isfile(path):
        return open(path).read().strip()
    return '?'


def _print_binary_version(base_dir, label):
    bin_name = 'vcpkg.exe' if sys.platform == 'win32' else 'vcpkg'
    bin_path = os.path.join(base_dir, bin_name)
    if os.path.isfile(bin_path):
        r = subprocess.run([bin_path, 'version'], capture_output=True, text=True)
        ver = r.stdout.strip() if r.returncode == 0 else r.stderr.strip()
        print('{}: {}'.format(label, ver))


def _show_version(label, ver):
    print('{}: {}'.format(label, ver))
