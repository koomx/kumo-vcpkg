import os
import platform as _platform
import sys


def detect_platform(force_musl=False):
    info = {
        'os': _detect_os(),
        'arch': _detect_arch(),
        'abi': None,
    }
    if info['os'] == 'linux':
        info['abi'] = _detect_linux_abi()
        if force_musl:
            info['abi'] = 'musl'
    return info


def _detect_os():
    raw = sys.platform.lower()
    if raw.startswith('linux'):
        return 'linux'
    if raw == 'darwin':
        return 'macos'
    if raw in ('win32', 'cygwin', 'msys'):
        return 'windows'
    raise RuntimeError('unsupported OS: ' + raw)


def _detect_arch():
    m = _platform.machine().lower()
    if m in ('x86_64', 'amd64'):
        return 'amd64'
    if m in ('aarch64', 'arm64'):
        return 'arm64'
    raise RuntimeError('unsupported arch: ' + m)


def _detect_linux_abi():
    if os.path.exists('/etc/alpine-release'):
        return 'musl'
    if os.path.exists('/etc/os-release'):
        with open('/etc/os-release') as f:
            for line in f:
                if line.startswith('ID=') and 'alpine' in line:
                    return 'musl'
    return 'glibc'
