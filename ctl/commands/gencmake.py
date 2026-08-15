"""Generate a new C++ project from kmcmake template"""
import os
import subprocess
import sys
import tempfile
import time
import shutil

import util
from bootstrap.log import Logger


COMMAND_NAME = 'gencmake'
KMCMAKE_REPO = 'https://github.com/koomx/kmcmake.git'


def setup(subparser):
    subparser.add_argument('name', nargs='?', help='project name')
    subparser.add_argument('-o', '--output', help='output directory for the new project')
    subparser.add_argument(
        '--enable-examples', action='store_true',
        help='install kmcmake teaching demos (foo / xxd / tests)')
    subparser.add_argument('--info', action='store_true', help='show kmcmake template info')
    subparser.set_defaults(func=run)


def run(args):
    log = Logger()

    if args.info:
        _show_info(log)
        return

    if not args.name or not args.output:
        log.err('name and --output are required (use --info to check template status)')
        sys.exit(1)

    pj_name = args.name
    out_dir = os.path.abspath(args.output)

    # Step 1: check output directory
    log.set_total(3)
    log.step('check output directory')
    log.detail('path', out_dir)
    if not os.path.isdir(out_dir):
        log.err('directory does not exist')
        sys.exit(1)
    for marker in ('CMakeLists.txt', 'CMakeCache.txt', 'SConstruct', 'Makefile'):
        path = os.path.join(out_dir, marker)
        if os.path.exists(path):
            log.err('already has a C/C++ project ({} found), refuse to overwrite'.format(marker))
            sys.exit(1)
    log.done()

    # Step 2: prepare kmcmake template
    log.step('prepare kmcmake template')
    template_dir = _ensure_template(log)
    version = _resolve_version()
    log.detail('version', version)
    log.done()

    # Step 3: configure and install via cmake
    log.step('generate project via cmake')
    log.detail('template', template_dir)
    log.detail('output', out_dir)
    log.detail('name', pj_name)

    build_dir = os.path.join(tempfile.mkdtemp(prefix='gencmake_'), 'build')
    os.makedirs(build_dir, exist_ok=True)
    log.detail('build', build_dir)

    cmake_cmd = ['cmake', '-S', template_dir, '-B', build_dir,
                 '-DCHANGEME=' + pj_name]
    if args.enable_examples:
        cmake_cmd.append('-DKMCMAKE_GEN_EXAMPLES=ON')
    log.detail('cmd', ' '.join(cmake_cmd))
    r = subprocess.run(cmake_cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log.err('cmake configure failed: ' + r.stderr.strip())
        shutil.rmtree(os.path.dirname(build_dir), ignore_errors=True)
        sys.exit(1)

    log.detail('cmd', 'cmake --install {} --prefix {}'.format(build_dir, out_dir))
    r = subprocess.run(
        ['cmake', '--install', build_dir, '--prefix', out_dir],
        capture_output=True, text=True)
    if r.returncode != 0:
        log.err('cmake install failed: ' + r.stderr.strip())
        shutil.rmtree(os.path.dirname(build_dir), ignore_errors=True)
        sys.exit(1)

    shutil.rmtree(os.path.dirname(build_dir), ignore_errors=True)
    log.done()


# -- template cache management ------------------------------------------------

def _cache_root():
    return os.path.join(util.vcpkg_root(), 'ctl', 'templates')


def _repo_dir():
    return os.path.join(_cache_root(), 'kmcmake_repo')


def _template_dir():
    return os.path.join(_repo_dir(), 'template')


def _ensure_template(log):
    repo = _repo_dir()
    tmpl = _template_dir()

    log.detail('cache', repo)
    if not os.path.isdir(repo):
        log.detail('action', 'clone from ' + KMCMAKE_REPO)
        os.makedirs(_cache_root(), exist_ok=True)
        r = subprocess.run(['git', 'clone', KMCMAKE_REPO, repo],
                           capture_output=True, text=True)
        if r.returncode != 0:
            log.err('clone failed: ' + r.stderr.strip())
            sys.exit(1)
    else:
        log.detail('action', 'fetch tags')
        r = subprocess.run(['git', '-C', repo, 'fetch', '--tags', '--force', 'origin'],
                           capture_output=True, text=True)
        if r.returncode != 0:
            log.warn('fetch failed, using local cache: ' + r.stderr.strip())

    tag = _latest_tag(repo)
    if tag:
        log.detail('tag', tag)
        r = subprocess.run(['git', '-C', repo, 'checkout', 'tags/' + tag],
                           capture_output=True, text=True)
        if r.returncode != 0:
            log.warn('checkout {} failed, keeping current: {}'.format(tag, r.stderr.strip()))
    else:
        log.warn('no tags found, keep current HEAD')

    if not os.path.isdir(tmpl):
        log.err('template/ not found in kmcmake repo')
        sys.exit(1)

    return tmpl


def _latest_tag(repo):
    try:
        r = subprocess.run(
            ['git', '-C', repo, 'tag', '--list', '--sort=-v:refname'],
            capture_output=True, text=True, check=True)
        tags = r.stdout.strip().splitlines()
        if tags:
            return tags[0]
    except subprocess.CalledProcessError:
        pass
    return None


def _resolve_version():
    tag = _latest_tag(_repo_dir())
    if tag:
        return tag.lstrip('v')
    return '1.0.0'


def _show_info(log):
    repo = _repo_dir()
    tmpl = _template_dir()

    if not os.path.isdir(repo):
        log.detail('cached', 'no')
        log.detail('clone', KMCMAKE_REPO)
        return

    current = '(unknown)'
    try:
        r = subprocess.run(
            ['git', '-C', repo, 'describe', '--tags', '--abbrev=0'],
            capture_output=True, text=True, check=True)
        current = r.stdout.strip()
    except subprocess.CalledProcessError:
        pass

    latest = _latest_tag(repo)

    updated = '(unknown)'
    try:
        r = subprocess.run(
            ['git', '-C', repo, 'log', '-1', '--format=%ct', 'HEAD'],
            capture_output=True, text=True, check=True)
        ts = int(r.stdout.strip())
        updated = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))
    except (subprocess.CalledProcessError, ValueError):
        pass

    all_tags = []
    try:
        r = subprocess.run(
            ['git', '-C', repo, 'tag', '--list', '--sort=-v:refname'],
            capture_output=True, text=True, check=True)
        all_tags = r.stdout.strip().splitlines()[:3]
    except subprocess.CalledProcessError:
        pass

    cached_ok = os.path.isdir(tmpl)

    log.detail('cached', 'yes' if cached_ok else 'yes (template/ missing!)')
    log.detail('path', repo)
    log.detail('checkout', current)
    log.detail('updated', updated)
    log.detail('latest tag', latest or '(none)')
    if all_tags:
        for t in all_tags:
            log.detail('  -', t)
