"""Publish ports to registry: update baseline, version files, commit"""
import json
import os
import subprocess
import sys
import time

from datetime import datetime, timezone


def setup(subparser):
    subparser.add_argument('-o', '--output', required=True,
                           help='target vcpkg repository path')
    subparser.add_argument('ports', nargs='+',
                           help='port name(s) to publish')
    subparser.set_defaults(func=run)


def run(args):
    output = os.path.abspath(args.output)
    ports = args.ports

    _check_git(output)
    dirty = _find_dirty_ports(output)
    _check_ports_coverage(dirty, ports)

    metas = _load_port_metas(output, ports)
    _update_baseline(output, metas)
    _first_commit(output, ports)
    _update_versions_with_tree(output, metas)
    _write_publish_txt(output, metas)
    _amend_commit(output, metas)


def _git(output, *cmd):
    return subprocess.run(
        ['git'] + list(cmd),
        cwd=output, capture_output=True, text=True
    )


def _check_git(output):
    r = _git(output, 'rev-parse', '--show-toplevel')
    if r.returncode != 0:
        print('error: {} is not a git repository'.format(output), file=sys.stderr)
        sys.exit(1)

    r = _git(output, 'status', '--porcelain')
    if not r.stdout.strip():
        print('error: no changes to publish'.format(output), file=sys.stderr)
        sys.exit(1)


def _find_dirty_ports(output):
    r = _git(output, 'status', '--porcelain', 'ports/')
    ports = set()
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        path = parts[1]
        if path == 'ports/' or path == 'ports':
            for name in sorted(os.listdir(os.path.join(output, 'ports'))):
                if os.path.isdir(os.path.join(output, 'ports', name)):
                    ports.add(name)
            break
        if path.startswith('ports/'):
            seg = path.split('/')
            if len(seg) >= 2 and seg[1]:
                ports.add(seg[1])
    return ports


def _check_ports_coverage(dirty, requested):
    missing = dirty - set(requested)
    if missing:
        print('error: the following ports have changes but were not included:',
              file=sys.stderr)
        for p in sorted(missing):
            print('  ' + p, file=sys.stderr)
        print('include them or discard changes before publishing', file=sys.stderr)
        sys.exit(1)


def _load_port_metas(output, ports):
    metas = {}
    missing = []
    for name in ports:
        mf = os.path.join(output, 'ports', name, 'vcpkg.json')
        if not os.path.isfile(mf):
            missing.append(name)
            continue
        with open(mf) as f:
            data = json.load(f)
        if data.get('name') != name:
            print('error: port {} has incorrect name {} in vcpkg.json'.format(
                name, data.get('name')), file=sys.stderr)
            sys.exit(1)
        metas[name] = {
            'version': data.get('version', '0.0.0'),
            'port-version': data.get('port-version', 0),
        }
    if missing:
        print('error: ports not found: {}'.format(', '.join(missing)), file=sys.stderr)
        sys.exit(1)
    return metas


def _update_baseline(output, metas):
    baseline_file = os.path.join(output, 'versions', 'baseline.json')
    baseline = {}
    if os.path.isfile(baseline_file):
        with open(baseline_file) as f:
            baseline = json.load(f)

    bl = baseline.setdefault('default', {})
    for name, m in metas.items():
        bl[name] = {'baseline': m['version'], 'port-version': m['port-version']}

    os.makedirs(os.path.dirname(baseline_file), exist_ok=True)
    with open(baseline_file, 'w') as f:
        json.dump(baseline, f, indent=4)
        f.write('\n')


def _first_commit(output, ports):
    r = _git(output, 'add', '-A')
    if r.returncode != 0:
        print('error: git add failed: {}'.format(r.stderr.strip()), file=sys.stderr)
        sys.exit(1)

    msg = 'publish: ' + ' '.join(ports)
    r = _git(output, 'commit', '-m', msg)
    if r.returncode != 0:
        print('warning: git commit failed: {}'.format(r.stderr.strip()))
        sys.exit(1)


def _update_versions_with_tree(output, metas):
    for name, m in metas.items():
        prefix = name[0].lower() + '-'
        vfile = os.path.join(output, 'versions', prefix, name + '.json')
        os.makedirs(os.path.dirname(vfile), exist_ok=True)

        existing_versions = []
        if os.path.isfile(vfile):
            with open(vfile) as f:
                data = json.load(f)
                existing_versions = data.get('versions', [])

        r = _git(output, 'rev-parse', 'HEAD:ports/{}'.format(name))
        if r.returncode != 0:
            print('warning: could not get tree hash for ports/{}'.format(name))
            git_tree = 'HEAD'
        else:
            git_tree = r.stdout.strip()

        entry = {
            'version': m['version'],
            'port-version': m['port-version'],
            'git-tree': git_tree,
        }

        found = False
        for i, v in enumerate(existing_versions):
            if v.get('version') == m['version'] and v.get('port-version') == m['port-version']:
                old_tree = v.get('git-tree', '')
                if old_tree == git_tree:
                    print('  warning: ports/{} tree hash unchanged ({})'.format(name, git_tree[:8]))
                existing_versions[i] = entry
                found = True
                break
        if not found:
            existing_versions.insert(0, entry)

        with open(vfile, 'w') as f:
            json.dump({'versions': existing_versions}, f, indent=2)
            f.write('\n')


def _write_publish_txt(output, metas):
    now = datetime.now(timezone.utc)
    lines = [
        '# publish summary start #####',
        'operator: vcpkgctl',
        'when: {}'.format(now.isoformat()),
        'ports.count: {}'.format(len(metas)),
    ]
    for name, m in metas.items():
        lines.append('port: {} {} (port-version {})'.format(name, m['version'], m['port-version']))
    lines.append('# publish summary end #####')
    lines.append('')

    summary = '\n'.join(lines)

    target = os.path.join(output, 'publish.txt')
    existing = ''
    if os.path.isfile(target):
        with open(target) as f:
            existing = f.read()

    with open(target, 'w') as f:
        f.write(summary)
        f.write(existing)


def _amend_commit(output, metas):
    r = _git(output, 'add', '-A')
    if r.returncode != 0:
        print('error: git add failed before amend: {}'.format(r.stderr.strip()), file=sys.stderr)
        sys.exit(1)

    r = _git(output, 'commit', '--amend', '--no-edit')
    if r.returncode != 0:
        print('error: git commit --amend failed: {}'.format(r.stderr.strip()), file=sys.stderr)
        sys.exit(1)

    names = list(metas.keys())
    print('published: ' + ', '.join(names))
