import os
import shutil
import stat
import subprocess
import sys
import tempfile

from bootstrap.tools import ensure_build_tools
from bootstrap.detect import detect_platform
from bootstrap.download import download_binary
from bootstrap.install import install_binary
from bootstrap.init import prepare_root
from bootstrap.env import setup_env
from bootstrap.log import Logger

VCPKG_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VCPKG_TOOL_REPO = 'https://github.com/koomx/vcpkg-tool.git'


def run_bootstrap(args=None):
    if args is None:
        args = {}

    log = Logger()

    n = 7 if args.get('disable_metrics') else 6
    log.set_total(n)

    _step_detect_platform(args, log)
    dl_path = _step_download(args, log)
    _step_install(dl_path, log)
    _step_init(log)
    _step_ensure_tools(log)
    _step_env(args, log)
    if args.get('disable_metrics'):
        _step_metrics(log)
    ok = _step_verify(log)
    if not ok:
        _step_build_from_source(log)

    log.complete()
    env_path = os.path.join(VCPKG_ROOT, '.env')
    print('  Source in your shell: source ' + env_path, flush=True)


def _step_detect_platform(args, log):
    log.step('Detecting platform')
    plat = detect_platform(force_musl=args.get('musl', False))
    log.detail('OS', plat['os'])
    log.detail('Arch', plat['arch'])
    if plat.get('abi'):
        log.detail('ABI', plat['abi'])
    log.done()
    args['_plat'] = plat


def _step_download(args, log):
    plat = args['_plat']
    from bootstrap.download import VERSION
    log.step('Downloading vcpkg binary {}'.format(VERSION))
    dl_path = download_binary(plat, log)
    log.done()
    return dl_path


def _step_install(dl_path, log):
    log.step('Installing binary')
    bin_path = install_binary(dl_path, VCPKG_ROOT)
    log.detail('Path', bin_path)
    log.done()
    return bin_path


def _step_init(log):
    log.step('Initializing root directory')
    prepare_root(VCPKG_ROOT)
    log.done()


def _step_ensure_tools(log):
    log.step('Ensuring build tools')
    ensure_build_tools(log)
    log.done()


def _step_env(args, log):
    plat = args['_plat']
    log.step('Configuring shell environment')
    setup_env(VCPKG_ROOT, plat['os'])
    log.done()


def _step_metrics(log):
    log.step('Disabling metrics')
    marker = os.path.join(VCPKG_ROOT, 'vcpkg.disable-metrics')
    if not os.path.isfile(marker):
        open(marker, 'w').close()
        log.ok('metrics disabled')
    log.done()


def _step_verify(log):
    log.step('Verifying installation')
    binary = os.path.join(VCPKG_ROOT, 'vcpkg.exe' if sys.platform == 'win32' else 'vcpkg')
    try:
        result = subprocess.run([binary, 'version'], capture_output=True, text=True)
        if result.returncode == 0:
            log.ok(result.stdout.strip())
            log.done()
            return True
        print('DEBUG verify: returncode={}, stdout={!r}, stderr={!r}'.format(
            result.returncode, result.stdout, result.stderr), flush=True)
        stderr = result.stderr.strip()
        if stderr:
            log.warn(stderr)
        return False
    except FileNotFoundError:
        log.warn('binary not found at ' + binary)
        return False
    except Exception as e:
        print('DEBUG verify exception: {!r}'.format(e), flush=True)
        return False


def _step_build_from_source(log):
    log.step('Building vcpkg from source')
    for tool in ('git', 'cmake'):
        if not shutil.which(tool):
            log.err('{} not available, cannot build from source'.format(tool))
            _print_final_hint()
            sys.exit(1)

    tmpdir = tempfile.mkdtemp(prefix='vcpkg-build-')
    try:
        src_dir = os.path.join(tmpdir, 'vcpkg-tool')
        build_dir = os.path.join(tmpdir, 'build')

        log.detail('Clone', VCPKG_TOOL_REPO)
        r = subprocess.run(
            ['git', 'clone', '--depth', '1', VCPKG_TOOL_REPO, src_dir],
            capture_output=True, text=True
        )
        if r.returncode != 0:
            log.err('git clone failed: ' + r.stderr.strip())
            _print_final_hint()
            sys.exit(1)
        log.ok('repository cloned')

        log.detail('Configuring', 'cmake ...')
        r = subprocess.run(
            ['cmake', '-S', src_dir, '-B', build_dir, '-DCMAKE_BUILD_TYPE=Release'],
            capture_output=True, text=True
        )
        if r.returncode != 0:
            log.err('cmake configure failed: ' + r.stderr.strip())
            _print_final_hint()
            sys.exit(1)

        log.detail('Building', 'cmake --build ...')
        r = subprocess.run(
            ['cmake', '--build', build_dir, '--parallel'],
            capture_output=True, text=True
        )
        if r.returncode != 0:
            log.err('cmake build failed: ' + r.stderr.strip())
            _print_final_hint()
            sys.exit(1)

        binary_name = 'vcpkg.exe' if sys.platform == 'win32' else 'vcpkg'
        built = os.path.join(build_dir, binary_name)
        if not os.path.isfile(built):
            log.err('build succeeded but binary not found at ' + built)
            _print_final_hint()
            sys.exit(1)

        dst = os.path.join(VCPKG_ROOT, binary_name)
        shutil.copy2(built, dst)
        st = os.stat(dst)
        os.chmod(dst, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        log.ok('built from source successfully')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    log.done()


def _print_final_hint():
    print('  Run: source ' + os.path.join(VCPKG_ROOT, '.env'), flush=True)
