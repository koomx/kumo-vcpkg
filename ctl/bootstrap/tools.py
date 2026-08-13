import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile


MIN_CMAKE_VERSION = (3, 31, 10)
MIN_CMAKE_VERSION_STR = '3.31.10'
_TOOLS_DIR = None


# ── public API ──────────────────────────────────────────────────────────

def ensure_build_tools(log=None):
    _init_tools_dir()
    if log:
        log.detail('cmake', 'checking...')
    ensure_cmake(log)
    if log:
        log.detail('ninja', 'checking...')
    ensure_ninja(log)
    if log:
        log.detail('make', 'checking...')
    ensure_make(log)
    _add_tools_to_path()


def tools_bin():
    return os.path.join(_vcpkg_root(), 'tools', 'bin')


# ── cmake ───────────────────────────────────────────────────────────────

def ensure_cmake(log=None):
    path = _find_system_cmake()
    if path and _check_cmake_version(path):
        _symlink_tool(path, 'cmake')
        if log:
            log.ok('cmake {}'.format(path))
        return path

    if log:
        log.detail('cmake', '>= {} required, attempting install'.format(MIN_CMAKE_VERSION_STR))

    for installer in (_install_cmake_via_pkg, _install_cmake_via_pip, _install_cmake_prebuilt, _build_cmake_source):
        path = installer(log)
        if path and _check_cmake_version(path):
            _symlink_tool(path, 'cmake')
            if log:
                log.ok('cmake {}'.format(path))
            return path

    raise RuntimeError('could not install cmake >= {}'.format(MIN_CMAKE_VERSION_STR))


def _find_system_cmake():
    return shutil.which('cmake')


def _check_cmake_version(path):
    try:
        r = subprocess.run([path, '--version'], capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            return False
        m = re.search(r'cmake\s+version\s+(\d+)\.(\d+)\.(\d+)', r.stdout)
        if not m:
            return False
        ver = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return ver >= MIN_CMAKE_VERSION
    except Exception:
        return False


def _install_cmake_via_pkg(log=None):
    if sys.platform == 'win32':
        if log:
            log.detail('pkg manager', 'choco')
        _run_cmd(['choco', 'install', 'cmake', '--installargs', 'ADD_CMAKE_TO_PATH=System', '-y'], log=log)
        for p in (r'C:\Program Files\CMake\bin\cmake.exe', r'C:\Program Files (x86)\CMake\bin\cmake.exe'):
            if os.path.isfile(p):
                return p
        return None

    if sys.platform == 'darwin':
        if log:
            log.detail('pkg manager', 'brew')
        _run_cmd(['brew', 'install', 'cmake'], log=log)
        return shutil.which('cmake')

    if shutil.which('apt-get'):
        if log:
            log.detail('pkg manager', 'apt')
        _run_cmd(['apt-get', 'update', '-qq'], log=log)
        _run_cmd(['apt-get', 'install', '-y', '-qq', 'cmake'], log=log)
        return shutil.which('cmake')

    if shutil.which('dnf'):
        if log:
            log.detail('pkg manager', 'dnf')
        _run_cmd(['dnf', 'install', '-y', 'cmake'], log=log)
        return shutil.which('cmake')

    if shutil.which('apk'):
        if log:
            log.detail('pkg manager', 'apk')
        _run_cmd(['apk', 'add', '--no-cache', 'cmake'], log=log)
        return shutil.which('cmake')
    return None


def _install_cmake_via_pip(log=None):
    pip = shutil.which('pip3') or shutil.which('pip')
    if not pip:
        if log:
            log.detail('pip', 'not found, installing')
        if shutil.which('apk'):
            _run_cmd(['apk', 'add', '--no-cache', 'py3-pip'], log=log)
        elif shutil.which('apt-get'):
            _run_cmd(['apt-get', 'install', '-y', '-qq', 'python3-pip'], log=log)
        elif shutil.which('dnf'):
            _run_cmd(['dnf', 'install', '-y', 'python3-pip'], log=log)
        pip = shutil.which('pip3') or shutil.which('pip')
    if not pip:
        return None

    if log:
        log.detail('pip', pip)
    env = os.environ.copy()
    env['PIP_REQUIRE_VIRTUALENV'] = '0'
    ok = _run_cmd([pip, 'install', 'cmake>=' + MIN_CMAKE_VERSION_STR], log=log, env=env)
    if not ok:
        ok = _run_cmd([pip, 'install', '--break-system-packages', 'cmake>=' + MIN_CMAKE_VERSION_STR], log=log, env=env)

    pip_bin = os.path.dirname(os.path.abspath(pip))
    os.environ['PATH'] = pip_bin + os.pathsep + os.environ.get('PATH', '')
    parent_bin = os.path.join(os.path.dirname(pip_bin), 'bin')
    if os.path.isdir(parent_bin):
        os.environ['PATH'] = parent_bin + os.pathsep + os.environ.get('PATH', '')

    cmake_bin = shutil.which('cmake')
    if cmake_bin and _check_cmake_version(cmake_bin):
        return cmake_bin

    for d in (parent_bin, os.path.join(pip_bin, '..', 'Scripts')):
        p = os.path.join(os.path.abspath(d), 'cmake' + ('.exe' if sys.platform == 'win32' else ''))
        if os.path.isfile(p):
            return p
    return None


def _install_cmake_prebuilt(log=None):
    dst = _cache_dir()
    arch = _cmake_prebuilt_arch()
    if not arch:
        return None

    ext = '.zip' if sys.platform == 'win32' else '.tar.gz'
    url = 'https://github.com/Kitware/CMake/releases/download/v{}/cmake-{}-{}{}'.format(
        MIN_CMAKE_VERSION_STR, MIN_CMAKE_VERSION_STR, arch, ext)
    archive = os.path.join(dst, 'cmake-{}{}'.format(MIN_CMAKE_VERSION_STR, ext))

    if log:
        log.detail('download', url)

    try:
        urllib.request.urlretrieve(url, archive)
    except Exception as e:
        if log:
            log.detail('download failed', str(e))
        return None

    extract_basename = 'cmake-{}-{}'.format(MIN_CMAKE_VERSION_STR, arch)
    extract_to = os.path.join(dst, extract_basename)
    if os.path.isdir(extract_to):
        shutil.rmtree(extract_to)

    try:
        if ext == '.zip':
            with zipfile.ZipFile(archive, 'r') as zf:
                zf.extractall(dst)
        else:
            with tarfile.open(archive, 'r:gz') as tf:
                tf.extractall(dst)
    except Exception as e:
        if log:
            log.detail('extract failed', str(e))
        return None

    cmake_bin = os.path.join(extract_to, 'bin', 'cmake' + ('.exe' if sys.platform == 'win32' else ''))
    if os.path.isfile(cmake_bin):
        return cmake_bin
    return None


def _cmake_prebuilt_arch():
    if sys.platform == 'win32':
        return 'windows-x86_64'
    if sys.platform == 'darwin':
        return 'macos-universal'
    m = _machine()
    if m == 'x86_64':
        return 'linux-x86_64'
    if m in ('aarch64', 'arm64'):
        return 'linux-aarch64'
    return None


def _build_cmake_source(log=None):
    if not shutil.which('make') and not shutil.which('ninja'):
        if log:
            log.detail('build from source', 'no make or ninja, skipped')
        return None

    cc = shutil.which('gcc') or shutil.which('cc') or shutil.which('cl')
    cxx = shutil.which('g++') or shutil.which('c++') or shutil.which('cl')
    if not cc or not cxx:
        if log:
            log.detail('build from source', 'no C/C++ compiler, skipped')
        return None

    if log:
        log.detail('build from source', 'cmake-{}'.format(MIN_CMAKE_VERSION_STR))

    tarball = 'cmake-{}.tar.gz'.format(MIN_CMAKE_VERSION_STR)
    url = 'https://github.com/Kitware/CMake/releases/download/v{}/{}'.format(MIN_CMAKE_VERSION_STR, tarball)
    dst = _cache_dir()
    archive = os.path.join(dst, tarball)
    src_dir = os.path.join(dst, 'cmake-{}-src'.format(MIN_CMAKE_VERSION_STR))

    try:
        urllib.request.urlretrieve(url, archive)
    except Exception as e:
        if log:
            log.detail('download failed', str(e))
        return None

    if os.path.isdir(src_dir):
        shutil.rmtree(src_dir)
    os.makedirs(src_dir, exist_ok=True)

    try:
        with tarfile.open(archive, 'r:gz') as tf:
            tf.extractall(dst)
    except Exception as e:
        if log:
            log.detail('extract failed', str(e))
        return None

    extracted = os.path.join(dst, 'cmake-{}'.format(MIN_CMAKE_VERSION_STR))
    if os.path.isdir(extracted):
        src_dir = extracted

    build_dir = os.path.join(dst, 'cmake-{}-build'.format(MIN_CMAKE_VERSION_STR))
    os.makedirs(build_dir, exist_ok=True)

    if log:
        log.detail('configuring', 'cmake ...')
    r = subprocess.run(
        ['sh', 'bootstrap', '--prefix=' + dst],
        cwd=src_dir, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        if log:
            log.detail('bootstrap failed', r.stderr.strip()[:500])
        return None

    if log:
        log.detail('building', 'make ...')
    r = subprocess.run(
        ['make', '-j', str(_cpu_count())],
        cwd=src_dir, capture_output=True, text=True, timeout=1200)
    if r.returncode != 0:
        if log:
            log.detail('build failed', r.stderr.strip()[:500])
        return None

    r = subprocess.run(
        ['make', 'install'],
        cwd=src_dir, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        if log:
            log.detail('install failed', r.stderr.strip()[:500])
        return None

    cmake_bin = os.path.join(dst, 'bin', 'cmake')
    if os.path.isfile(cmake_bin):
        return cmake_bin
    return None


# ── ninja ───────────────────────────────────────────────────────────────

def ensure_ninja(log=None):
    path = _find_ninja()
    if path:
        _symlink_tool(path, 'ninja')
        if log:
            log.ok('ninja {}'.format(path))
        return path

    if log:
        log.detail('ninja', 'not found, attempting install')

    # 1) system package manager
    path = _install_ninja_via_pkg(log)
    if not path:
        # 2) build from source (avoids glibc prebuilt incompatibility on musl)
        path = _build_ninja_source(log)
    if path:
        _symlink_tool(path, 'ninja')
        if log:
            log.ok('ninja {}'.format(path))
        return path

    if log:
        log.warn('ninja not available')
    return None


def _install_ninja_via_pkg(log=None):
    if sys.platform == 'win32':
        if log:
            log.detail('pkg manager', 'choco')
        _run_cmd(['choco', 'install', 'ninja', '-y'], log=log)
        return shutil.which('ninja') or shutil.which('ninja.exe')

    if sys.platform == 'darwin':
        if log:
            log.detail('pkg manager', 'brew')
        _run_cmd(['brew', 'install', 'ninja'], log=log)
        return shutil.which('ninja')

    if shutil.which('apt-get'):
        if log:
            log.detail('pkg manager', 'apt')
        _run_cmd(['apt-get', 'install', '-y', '-qq', 'ninja-build'], log=log)
        return shutil.which('ninja')

    if shutil.which('dnf'):
        if log:
            log.detail('pkg manager', 'dnf')
        _run_cmd(['dnf', 'install', '-y', 'ninja-build'], log=log)
        return shutil.which('ninja')

    if shutil.which('apk'):
        if log:
            log.detail('pkg manager', 'apk')
        for pkg in ('ninja-build', 'ninja'):
            _run_cmd(['apk', 'add', '--no-cache', pkg], log=log)
            found = _find_ninja()
            if found:
                return found
        return None
    return None


def _find_ninja():
    p = shutil.which('ninja')
    if p:
        return p
    for d in ('/usr/bin', '/usr/local/bin', '/usr/lib/ninja/bin', '/usr/libexec',
              '/usr/lib/ninja-build/bin'):
        p = os.path.join(d, 'ninja')
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    try:
        r = subprocess.run(['which', 'ninja'], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            p = r.stdout.strip()
            if p and os.path.isfile(p):
                return p
    except Exception:
        pass
    # Search entire /usr for ninja
    try:
        r = subprocess.run(['find', '/usr', '-name', 'ninja', '-type', 'f'],
                          capture_output=True, text=True, timeout=10)
        for line in r.stdout.strip().splitlines():
            p = line.strip()
            if p and os.access(p, os.X_OK):
                return p
    except Exception:
        pass
    return None


def _install_ninja_prebuilt(log=None):
    dst = _cache_dir()
    arch = _ninja_prebuilt_arch()
    if not arch:
        return None

    url = 'https://github.com/ninja-build/ninja/releases/download/v1.12.1/ninja-{}.zip'.format(arch)
    archive = os.path.join(dst, 'ninja-{}.zip'.format(arch))

    if log:
        log.detail('download', url)

    try:
        urllib.request.urlretrieve(url, archive)
    except Exception as e:
        if log:
            log.detail('download failed', str(e))
        return None

    try:
        with zipfile.ZipFile(archive, 'r') as zf:
            zf.extractall(dst)
    except Exception as e:
        if log:
            log.detail('extract failed', str(e))
        return None

    ninja_bin = os.path.join(dst, 'ninja' + ('.exe' if sys.platform == 'win32' else ''))
    if os.path.isfile(ninja_bin):
        return ninja_bin
    return None


def _ninja_prebuilt_arch():
    if sys.platform == 'win32':
        return 'win'
    if sys.platform == 'darwin':
        return 'mac'
    m = _machine()
    if m == 'x86_64':
        return 'linux'
    if m in ('aarch64', 'arm64'):
        return 'linux-aarch64'
    return None


def _build_ninja_source(log=None):
    if not shutil.which('cmake'):
        if log:
            log.detail('build from source', 'cmake not available, skipped')
        return None

    cc = shutil.which('gcc') or shutil.which('cc') or shutil.which('cl')
    cxx = shutil.which('g++') or shutil.which('c++') or shutil.which('cl')
    if not cc or not cxx:
        if log:
            log.detail('build from source', 'no C/C++ compiler, skipped')
        return None

    if log:
        log.detail('build from source', 'ninja ...')

    dst = _cache_dir()
    src_dir = os.path.join(dst, 'ninja-src')

    r = subprocess.run(
        ['git', 'clone', '--depth', '1', '-b', 'v1.12.1',
         'https://github.com/ninja-build/ninja.git', src_dir],
        capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        if log:
            log.detail('clone failed', r.stderr.strip()[:200])
        return None

    build_dir = os.path.join(dst, 'ninja-build')
    os.makedirs(build_dir, exist_ok=True)

    r = subprocess.run(
        ['cmake', '-S', src_dir, '-B', build_dir, '-DCMAKE_BUILD_TYPE=Release'],
        capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        if log:
            log.detail('configure failed', r.stderr.strip()[:500])
        return None

    r = subprocess.run(
        ['cmake', '--build', build_dir, '--parallel'],
        capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        if log:
            log.detail('build failed', r.stderr.strip()[:500])
        return None

    ninja_bin = os.path.join(build_dir, 'ninja' + ('.exe' if sys.platform == 'win32' else ''))
    if os.path.isfile(ninja_bin):
        return ninja_bin
    return None


# ── make ────────────────────────────────────────────────────────────────

def ensure_make(log=None):
    if sys.platform == 'win32':
        return

    path = shutil.which('make')
    if path:
        _symlink_tool(path, 'make')
        if log:
            log.ok('make {}'.format(path))
        return path

    if log:
        log.detail('make', 'not found, attempting install')

    if shutil.which('apt-get'):
        _run_cmd(['apt-get', 'install', '-y', '-qq', 'build-essential'], log=log)
    elif shutil.which('apk'):
        _run_cmd(['apk', 'add', '--no-cache', 'build-base'], log=log)
    elif shutil.which('dnf'):
        _run_cmd(['dnf', 'install', '-y', 'make'], log=log)
    elif sys.platform == 'darwin':
        if log:
            log.detail('make', 'install Xcode CLT: xcode-select --install')

    path = shutil.which('make')
    if path:
        _symlink_tool(path, 'make')
        if log:
            log.ok('make {}'.format(path))
    return path


# ── helpers ─────────────────────────────────────────────────────────────

def _vcpkg_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _init_tools_dir():
    d = tools_bin()
    os.makedirs(d, exist_ok=True)


def _symlink_tool(src, name):
    dst = os.path.join(tools_bin(), name + ('.exe' if sys.platform == 'win32' else ''))
    # Ensure source is executable
    st = os.stat(src)
    if not (st.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)):
        os.chmod(src, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    try:
        if os.path.islink(dst) or os.path.isfile(dst):
            os.remove(dst)
        os.symlink(src, dst)
    except (OSError, AttributeError):
        shutil.copy2(src, dst)
        os.chmod(dst, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _add_tools_to_path():
    path = tools_bin()
    if path not in os.environ.get('PATH', ''):
        os.environ['PATH'] = path + os.pathsep + os.environ.get('PATH', '')


def _cache_dir():
    global _TOOLS_DIR
    if _TOOLS_DIR is None:
        _TOOLS_DIR = os.path.join(tempfile.gettempdir(), 'vcpkg-tools')
        os.makedirs(_TOOLS_DIR, exist_ok=True)
    return _TOOLS_DIR


def _run_cmd(cmd, log=None, **kwargs):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, **kwargs)
        if r.returncode == 0:
            return True
        if log:
            log.detail('cmd failed', ' '.join(cmd))
            if r.stderr.strip():
                log.detail('stderr', r.stderr.strip()[:200])
        return False
    except Exception as e:
        if log:
            log.detail('cmd error', str(e))
        return False


def _machine():
    import platform
    m = platform.machine().lower()
    if m in ('x86_64', 'amd64'):
        return 'x86_64'
    if m in ('aarch64', 'arm64'):
        return 'aarch64'
    return m


def _cpu_count():
    try:
        return os.cpu_count() or 2
    except Exception:
        return 2


def _is_musl():
    if os.path.exists('/etc/alpine-release'):
        return True
    try:
        with open('/etc/os-release') as f:
            return 'alpine' in f.read()
    except Exception:
        return False
