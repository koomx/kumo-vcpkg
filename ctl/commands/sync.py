"""Update baseline in vcpkg-configuration.json to latest registry HEAD"""
import json
import os
import subprocess
import sys

import util


COMMAND_NAME = 'sync'


def setup(subparser):
    subparser.set_defaults(func=run)


def run(args):
    project_dir = os.getcwd()
    cfg_file = os.path.join(project_dir, 'vcpkg-configuration.json')

    if not os.path.isfile(cfg_file):
        print('not a vcpkg project directory (vcpkg-configuration.json not found)')
        return

    with open(cfg_file) as f:
        cfg = json.load(f)

    vcpkg_root = util.vcpkg_root()
    registry_url = _read_registry_url(vcpkg_root)
    if not registry_url:
        print('warning: registry.txt not found or empty in ' + vcpkg_root)
        registry_url = _normalize_url('https://github.com/koomx/kumo-vcpkg.git')

    _git(vcpkg_root, 'fetch', 'origin')
    r = _git(vcpkg_root, 'rev-parse', 'origin/master')
    if r.returncode != 0:
        print('error: could not get HEAD from registry', file=sys.stderr)
        sys.exit(1)
    latest_hash = r.stdout.strip()

    changed = False

    if 'default-registry' in cfg:
        reg = cfg['default-registry']
        if _update_registry(reg, registry_url, latest_hash, 'default-registry'):
            changed = True

    for i, reg in enumerate(cfg.get('registries', [])):
        key = 'registries[{}]'.format(i)
        if _update_registry(reg, registry_url, latest_hash, key):
            changed = True

    if changed:
        with open(cfg_file, 'w') as f:
            json.dump(cfg, f, indent=2)
            f.write('\n')
        print('updated: ' + cfg_file)
    else:
        print('no changes made')


def _read_registry_url(vcpkg_root):
    path = os.path.join(vcpkg_root, 'registry.txt')
    if os.path.isfile(path):
        with open(path) as f:
            return f.readline().strip()
    return ''


def _update_registry(reg, registry_url, latest_hash, key):
    if reg.get('kind') != 'git':
        print('  skip {}: kind is "{}", not git'.format(key, reg.get('kind', 'unknown')))
        return False

    repo_url = reg.get('repository', '')
    if _normalize_url(repo_url) != _normalize_url(registry_url):
        print('  skip {}: repository "{}" does not match active registry "{}"'.format(
            key, repo_url, registry_url))
        return False

    old = reg.get('baseline', '')
    if old == latest_hash:
        print('  {}: already up to date ({})'.format(key, latest_hash[:8]))
        return False

    reg['baseline'] = latest_hash
    print('  {}: {} -> {}'.format(key, old[:8] if old else 'none', latest_hash[:8]))
    return True


def _normalize_url(url):
    url = url.strip()
    if url.endswith('.git'):
        url = url[:-4]
    if url.endswith('/'):
        url = url[:-1]
    return url


def _git(cwd, *cmd):
    return subprocess.run(
        ['git'] + list(cmd),
        cwd=cwd, capture_output=True, text=True
    )
