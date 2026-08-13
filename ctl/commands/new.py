"""Create a new vcpkg repository"""
import json
import os
import re
import shutil
import subprocess
import sys

import util
from commands.publish import run as publish_run


_INFRA_DIRS = ['scripts', 'triplets', 'ctl', 'docs']
_INFRA_FILES = ['vcpkgctl', 'vcpkgctl.bat']
_AUX_FILES = ['.vcpkg-root', 'ports.txt', 'README.md']


def setup(subparser):
    subparser.add_argument('dir', help='target directory for the new repository')
    subparser.add_argument('-r', '--remote', required=True,
                           help='remote registry URL (https:// or http:// only)')
    subparser.set_defaults(func=run)


def run(args):
    target = os.path.abspath(args.dir)
    remote = args.remote

    if not re.match(r'^https?://', remote):
        print('error: remote must be an http/https URL, got: {}'.format(remote), file=sys.stderr)
        sys.exit(1)

    _prepare_dir(target)
    template = util.vcpkg_root()

    _copy_infrastructure(template, target)
    _write_registry(target, remote)
    _ensure_vcpkg_root(target)
    _add_keep_files(target)

    _copy_builtin_ports(template, target)
    _copy_versions(template, target)

    _publish_builtin_ports(target)

    print('new repository created at ' + target)


def _prepare_dir(target):
    if os.path.isdir(target):
        git_dir = os.path.join(target, '.git')
        if not os.path.isdir(git_dir):
            print('error: {} exists but is not a git repository'.format(target), file=sys.stderr)
            sys.exit(1)
        print('using existing git repository: ' + target)
    else:
        os.makedirs(target, exist_ok=True)
        subprocess.run(['git', 'init'], cwd=target, check=True, capture_output=True)
        print('initialized git repository: ' + target)


def _copy_infrastructure(template, target):
    for name in _INFRA_DIRS:
        src = os.path.join(template, name)
        dst = os.path.join(target, name)
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        if os.path.isdir(src):
            shutil.copytree(src, dst, symlinks=True,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            print('  copied ' + name + '/')

    for name in _INFRA_FILES:
        src = os.path.join(template, name)
        dst = os.path.join(target, name)
        if os.path.isfile(src):
            shutil.copy2(src, dst)
            print('  copied ' + name)

    for name in _AUX_FILES:
        src = os.path.join(template, name)
        dst = os.path.join(target, name)
        if os.path.isfile(src):
            shutil.copy2(src, dst)


def _write_registry(target, remote):
    path = os.path.join(target, 'registry.txt')
    with open(path, 'w') as f:
        f.write(remote + '\n')
    print('  wrote registry.txt')


def _ensure_vcpkg_root(target):
    path = os.path.join(target, '.vcpkg-root')
    if not os.path.isfile(path):
        open(path, 'w').close()


def _add_keep_files(target):
    empty_dirs = _find_empty_dirs(target)
    for d in empty_dirs:
        keep = os.path.join(d, '.keep')
        if not os.path.isfile(keep):
            open(keep, 'w').close()


def _find_empty_dirs(root):
    result = []
    for dirpath, dirnames, filenames in os.walk(root):
        if '.git' in dirpath:
            continue
        if not dirnames and not filenames:
            result.append(dirpath)
        elif not dirnames and filenames == ['.keep']:
            result.append(dirpath)
    return result


def _copy_builtin_ports(template, target):
    ports_src = os.path.join(template, 'ports')
    ports_dst = os.path.join(target, 'ports')
    os.makedirs(ports_dst, exist_ok=True)

    for name in sorted(os.listdir(ports_src)):
        if not name.startswith('vcpkg-'):
            continue
        src = os.path.join(ports_src, name)
        dst = os.path.join(ports_dst, name)
        if not os.path.isdir(src):
            continue
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        print('  copied ports/' + name)


def _copy_versions(template, target):
    template_root = util.vcpkg_root()
    ports_src = os.path.join(template_root, 'ports')
    builtin = sorted(
        name for name in os.listdir(ports_src)
        if name.startswith('vcpkg-') and os.path.isdir(os.path.join(ports_src, name))
    )

    versions_dst = os.path.join(target, 'versions')
    if os.path.isdir(versions_dst):
        shutil.rmtree(versions_dst)
    os.makedirs(versions_dst, exist_ok=True)

    for name in builtin:
        prefix = name[0].lower() + '-'
        vdir = os.path.join(versions_dst, prefix)
        os.makedirs(vdir, exist_ok=True)
        src = os.path.join(template_root, 'versions', prefix, name + '.json')
        dst = os.path.join(vdir, name + '.json')
        if os.path.isfile(src):
            shutil.copy2(src, dst)

    baseline_src = os.path.join(template_root, 'versions', 'baseline.json')
    baseline = {'default': {}}
    if os.path.isfile(baseline_src):
        with open(baseline_src) as f:
            data = json.load(f)
        for name in builtin:
            entry = data.get('default', {}).get(name)
            if entry:
                baseline['default'][name] = entry
    with open(os.path.join(versions_dst, 'baseline.json'), 'w') as f:
        json.dump(baseline, f, indent=4)
        f.write('\n')

    print('  copied versions/')


def _publish_builtin_ports(target):
    template = util.vcpkg_root()
    ports_src = os.path.join(template, 'ports')
    builtin = sorted(
        name for name in os.listdir(ports_src)
        if name.startswith('vcpkg-') and os.path.isdir(os.path.join(ports_src, name))
    )

    class Args:
        output = target
        ports = builtin

    print('  publishing {} built-in port(s)...'.format(len(builtin)))
    try:
        publish_run(Args())
    except SystemExit as e:
        if e.code != 0:
            print('error: publish failed for built-in ports', file=sys.stderr)
            sys.exit(1)
