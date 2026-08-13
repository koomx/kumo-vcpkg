import hashlib
import os
import subprocess
import sys
import tempfile
import urllib.request


VERSION = '2026-08-17'
BASE_URL = 'https://github.com/koomx/vcpkg-tool/releases/download/{VERSION}/{FILENAME}'
CHECKSUM_URL = 'https://github.com/koomx/vcpkg-tool/releases/download/{VERSION}/SHA256SUMS'


def _load_checksums(log=None):
    url = CHECKSUM_URL.format(VERSION=VERSION)
    try:
        resp = urllib.request.urlopen(url, timeout=30)
        data = resp.read().decode('utf-8')
        checksums = {}
        for line in data.strip().splitlines():
            parts = line.split()
            if len(parts) >= 2:
                checksums[parts[-1].lstrip('*')] = parts[0]
        return checksums
    except Exception as e:
        raise RuntimeError('failed to load checksums: {}'.format(e))


def download_binary(plat, log=None):
    name = _resolve_filename(plat)
    url = BASE_URL.format(VERSION=VERSION, FILENAME=name)
    dest = os.path.join(tempfile.gettempdir(), name)

    if log:
        log.detail('Binary', name)
        log.detail('URL', url)

    _do_download(url, dest, log)

    checksums = _load_checksums(log)
    expected = checksums.get(name)
    if expected:
        _verify_sha256(dest, expected, log)

    return dest


def _resolve_filename(plat):
    os_name = plat['os']
    arch = plat['arch']
    abi = plat.get('abi')

    if os_name == 'linux':
        if abi == 'musl':
            if arch != 'amd64':
                raise RuntimeError('no musl binary for arch {}'.format(arch))
            return 'vcpkg-muslc'
        if arch == 'arm64':
            return 'vcpkg-glibc-arm64'
        return 'vcpkg-glibc'

    if os_name == 'macos':
        return 'vcpkg-macos'

    if os_name == 'windows':
        if arch == 'arm64':
            return 'vcpkg-arm64.exe'
        return 'vcpkg.exe'

    raise RuntimeError('unknown platform: {} {}'.format(os_name, arch))


def _do_download(url, dest, log=None):
    if _try_urllib(url, dest, log):
        return
    if _try_curl(url, dest):
        return
    if _try_wget(url, dest):
        return
    raise RuntimeError('download failed: {}'.format(url))


CURL_TIMEOUT = 60


def _try_curl(url, dest):
    try:
        subprocess.run(
            ['curl', '-fsSL', '-o', dest, url],
            check=True, capture_output=True, timeout=CURL_TIMEOUT
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _try_wget(url, dest):
    try:
        subprocess.run(
            ['wget', '-q', '-O', dest, url],
            check=True, capture_output=True, timeout=CURL_TIMEOUT
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _try_urllib(url, dest, log=None):
    try:
        req = urllib.request.Request(url, method='HEAD')
        resp = urllib.request.urlopen(req, timeout=CURL_TIMEOUT)
        total = int(resp.headers.get('Content-Length', 0))
    except Exception:
        total = 0

    reporthook = None
    if log and total > 0:
        def reporthook(block_num, block_size, total_size):
            sofar = min(block_num * block_size, total)
            log.progress(sofar, total)

    try:
        urllib.request.urlretrieve(url, dest, reporthook)
        return True
    except Exception:
        return False


def _verify_sha256(filepath, expected, log=None):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    actual = h.hexdigest()
    if actual != expected:
        os.remove(filepath)
        raise RuntimeError(
            'SHA256 mismatch for {}: expected {}, got {}'.format(
                os.path.basename(filepath), expected, actual)
        )
    if log:
        log.ok('SHA256 verified')
