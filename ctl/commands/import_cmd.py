"""Import ports from another vcpkg repository"""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

COMMAND_NAME = 'import'
_META = 'vcpkg.json'


def setup(subparser):
    subparser.add_argument('-i', '--input', required=True,
                           help='source vcpkg repository path')
    subparser.add_argument('-o', '--output', required=True,
                           help='target vcpkg repository path')
    subparser.add_argument('ports', nargs='*', help='port name(s) to import')
    subparser.add_argument('--all', action='store_true',
                           help='import all ports from source')
    subparser.set_defaults(func=run)


def run(args):
    src = os.path.abspath(args.input)
    dst = os.path.abspath(args.output)

    _check_input(src)
    _check_output(dst)

    ports = _resolve_ports(args, src)
    if not ports:
        print('nothing to import')
        return

    for name in ports:
        print('  import: ' + name)

    _copy_ports(src, dst, ports)
    _update_baseline(src, dst, ports)
    _copy_versions(src, dst, ports)
    _first_commit(dst, ports)
    _update_git_tree(dst, ports)
    _write_import_txt(src, dst, ports)
    _amend_commit(dst)

    print('imported: {} port(s)'.format(len(ports)))


def _check_input(src):
    r = _git(src, 'rev-parse', '--show-toplevel')
    if r.returncode != 0:
        print('error: input is not a git repository: ' + src, file=sys.stderr)
        sys.exit(1)
    r = _git(src, 'status', '--porcelain')
    if r.stdout.strip():
        print('error: input repository has uncommitted changes, commit or stash first',
              file=sys.stderr)
        sys.exit(1)


def _check_output(dst):
    r = _git(dst, 'rev-parse', '--show-toplevel')
    if r.returncode != 0:
        print('error: output is not a git repository: ' + dst, file=sys.stderr)
        sys.exit(1)


def _resolve_ports(args, src):
    raw = args.ports
    if args.all:
        raw = _list_all_ports(src)
    if not raw:
        print('error: specify ports or use --all', file=sys.stderr)
        sys.exit(1)

    all_deps = set()
    for name in raw:
        _collect_deps(src, name, all_deps)

    return _topological_sort(src, list(all_deps))


def _list_all_ports(src):
    ports_dir = os.path.join(src, 'ports')
    if not os.path.isdir(ports_dir):
        return []
    result = []
    for name in sorted(os.listdir(ports_dir)):
        mf = os.path.join(ports_dir, name, _META)
        if os.path.isfile(mf) and os.path.isdir(os.path.join(ports_dir, name)):
            result.append(name)
    return result


def _collect_deps(src, port, visited):
    if port in visited:
        return
    visited.add(port)
    mf = os.path.join(src, 'ports', port, _META)
    if not os.path.isfile(mf):
        return
    try:
        with open(mf) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return

    for dep in data.get('dependencies', []):
        if isinstance(dep, str):
            name = dep
        elif isinstance(dep, dict):
            name = dep.get('name', '')
        else:
            continue
        if name:
            _collect_deps(src, name, visited)


def _topological_sort(src, ports):
    graph = {p: set() for p in ports}
    for p in ports:
        mf = os.path.join(src, 'ports', p, _META)
        if not os.path.isfile(mf):
            continue
        try:
            with open(mf) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        for dep in data.get('dependencies', []):
            if isinstance(dep, str):
                name = dep
            elif isinstance(dep, dict):
                name = dep.get('name', '')
            else:
                continue
            if name and name in graph:
                graph[p].add(name)

    result = []
    visited = set()
    temp = set()

    def dfs(n):
        if n in temp:
            return
        if n in visited:
            return
        temp.add(n)
        for dep in graph.get(n, set()):
            if dep in graph:
                dfs(dep)
        temp.remove(n)
        visited.add(n)
        result.append(n)

    for p in ports:
        if p not in visited:
            dfs(p)

    return result


def _copy_ports(src, dst, ports):
    for name in ports:
        src_port = os.path.join(src, 'ports', name)
        dst_port = os.path.join(dst, 'ports', name)
        if not os.path.isdir(src_port):
            print('  warning: port {} not found in source, skipping'.format(name))
            continue
        if os.path.isdir(dst_port):
            print('  skip {}: already exists in target'.format(name))
            continue
        os.makedirs(os.path.dirname(dst_port), exist_ok=True)
        shutil.copytree(src_port, dst_port)
        print('  copied: ' + name)


def _update_baseline(src, dst, ports):
    src_bl = _load_baseline(src)
    dst_bl = _load_baseline(dst)

    for name in ports:
        entry = _get_baseline_entry(src_bl, name)
        if not entry:
            continue
        bl = dst_bl.setdefault('default', {})
        if name in bl:
            continue
        bl[name] = entry

    bl_file = os.path.join(dst, 'versions', 'baseline.json')
    os.makedirs(os.path.dirname(bl_file), exist_ok=True)
    with open(bl_file, 'w') as f:
        json.dump(dst_bl, f, indent=4)
        f.write('\n')


def _load_baseline(root):
    path = os.path.join(root, 'versions', 'baseline.json')
    if os.path.isfile(path):
        with open(path) as f:
            return json.load(f)
    return {}


def _get_baseline_entry(baseline, name):
    bl = baseline.get('default', {})
    return bl.get(name)


def _copy_versions(src, dst, ports):
    for name in ports:
        prefix = name[0].lower() + '-'
        dst_vdir = os.path.join(dst, 'versions', prefix)
        os.makedirs(dst_vdir, exist_ok=True)
        dst_vfile = os.path.join(dst_vdir, name + '.json')
        if os.path.isfile(dst_vfile):
            continue

        src_vfile = os.path.join(src, 'versions', prefix, name + '.json')
        if not os.path.isfile(src_vfile):
            print('  warning: version file not found for ' + name)
            _write_empty_version(dst_vfile)
            continue

        shutil.copy2(src_vfile, dst_vfile)


def _write_empty_version(path):
    entry = {
        'version': '0.0.0',
        'port-version': 0,
        'git-tree': 'HEAD',
    }
    data = {'versions': [entry]}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')


def _first_commit(dst, ports):
    r = _git(dst, 'add', '-A')
    if r.returncode != 0:
        print('error: git add failed: ' + r.stderr.strip(), file=sys.stderr)
        sys.exit(1)

    msg = 'import: ' + ' '.join(ports)
    r = _git(dst, 'commit', '-m', msg)
    if r.returncode != 0:
        print('warning: git commit failed: ' + r.stderr.strip())
        sys.exit(1)


def _update_git_tree(dst, ports):
    bl = _load_baseline(dst)

    for name in ports:
        port_dir = os.path.join(dst, 'ports', name)
        if not os.path.isdir(port_dir):
            continue

        bl_entry = bl.get('default', {}).get(name)
        if not bl_entry:
            continue

        prefix = name[0].lower() + '-'
        vfile = os.path.join(dst, 'versions', prefix, name + '.json')
        if not os.path.isfile(vfile):
            continue

        r = _git(dst, 'rev-parse', 'HEAD:ports/' + name)
        if r.returncode != 0:
            print('  warning: could not get tree hash for ports/' + name)
            continue
        git_tree = r.stdout.strip()

        with open(vfile) as f:
            vdata = json.load(f)

        baseline_ver = bl_entry.get('baseline', '')
        baseline_pv = bl_entry.get('port-version', 0)
        updated = False
        for entry in vdata.get('versions', []):
            if (entry.get('version') == baseline_ver
                    and entry.get('port-version') == baseline_pv):
                if entry.get('git-tree') == git_tree:
                    print('  warning: ports/{} tree hash unchanged ({})'.format(name, git_tree[:8]))
                entry['git-tree'] = git_tree
                updated = True
                break

        if updated:
            with open(vfile, 'w') as f:
                json.dump(vdata, f, indent=2)
                f.write('\n')


def _write_import_txt(src, dst, ports):
    r = _git(src, 'remote', 'get-url', 'origin')
    remote_url = r.stdout.strip() if r.returncode == 0 else ''

    r = _git(src, 'log', '-1',
             '--format=%H|||%an|||%ad|||%s')
    log_line = r.stdout.strip() if r.returncode == 0 else ''
    parts = log_line.split('|||') if log_line else [''] * 4

    now = datetime.now(timezone.utc)
    lines = [
        '# import summary start #####',
        'operator: vcpkgctl',
        'when: {}'.format(now.isoformat()),
        'original.hash: {}'.format(parts[0] if len(parts) > 0 else ''),
        'original.author: {}'.format(parts[1] if len(parts) > 1 else ''),
        'original.date: {}'.format(parts[2] if len(parts) > 2 else ''),
        'original.message: {}'.format(parts[3] if len(parts) > 3 else ''),
        'original.remote: {}'.format(remote_url),
        'ports.count: {}'.format(len(ports)),
    ]
    for name in ports:
        lines.append('port: {}'.format(name))
    lines.append('# import summary end #####')
    lines.append('')

    summary = '\n'.join(lines)

    target = os.path.join(dst, 'import.txt')
    existing = ''
    if os.path.isfile(target):
        with open(target) as f:
            existing = f.read()
    with open(target, 'w') as f:
        f.write(summary)
        f.write(existing)


def _amend_commit(dst):
    r = _git(dst, 'add', '-A')
    if r.returncode != 0:
        print('error: git add failed before amend: ' + r.stderr.strip(), file=sys.stderr)
        sys.exit(1)
    r = _git(dst, 'commit', '--amend', '--no-edit')
    if r.returncode != 0:
        print('error: git commit --amend failed: ' + r.stderr.strip(), file=sys.stderr)
        sys.exit(1)


def _git(cwd, *cmd):
    return subprocess.run(
        ['git'] + list(cmd),
        cwd=cwd, capture_output=True, text=True
    )
