import os
import re
import sys


def setup_env(vcpkg_root, os_name):
    if os_name == 'windows':
        _setup_windows_env(vcpkg_root)
        return

    env_path = os.path.join(vcpkg_root, '.env')
    tools_bin = os.path.join(vcpkg_root, 'tools', 'bin')
    lines = [
        'export VCPKG_ROOT=' + vcpkg_root,
        'export PATH=$PATH:$VCPKG_ROOT:' + tools_bin,
        'export VCPKG_FORCE_SYSTEM_BINARIES=1',
    ]
    _write_env(env_path, lines)
    _apply_env(lines)
    _upgrade_shell_env(vcpkg_root, env_path)
    print('  Environment: source ' + env_path, flush=True)


def _setup_windows_env(vcpkg_root):
    from plat import set_env_vars
    set_env_vars(vcpkg_root)


def _write_env(env_path, lines):
    content = '\n'.join(lines) + '\n'
    with open(env_path, 'w') as f:
        f.write(content)


def _apply_env(lines):
    for line in lines:
        if line.startswith('export '):
            var_val = line[7:]
            eq = var_val.find('=')
            if eq > 0:
                key = var_val[:eq]
                val = var_val[eq + 1:]
                os.environ[key] = os.path.expandvars(val)


def _completion_line(vcpkg_root):
    shell = os.environ.get('SHELL', '')
    base = os.path.join(vcpkg_root, 'scripts', 'vcpkg_completion')
    if 'zsh' in shell:
        return 'source ' + base + '.zsh'
    if 'fish' in shell:
        return 'source ' + base + '.fish'
    if 'bash' in shell or not shell:
        p = base + '.bash'
        if os.path.isfile(p):
            return 'source ' + p
    return ''


_OLD_ENV_MARKER = '# vcpkgctl environment'
_NEW_SOURCE_LINE = None


def _upgrade_shell_env(vcpkg_root, env_path):
    from plat import get_shell_files
    files = get_shell_files()
    source_line = 'source ' + env_path

    for filepath in files:
        if not os.path.isfile(filepath):
            continue
        with open(filepath) as f:
            content = f.read()

        original = content

        # Remove old multi-line block (both 3-line and any variant)
        pattern = re.compile(r'\n?' + re.escape(_OLD_ENV_MARKER) + r'\n.*?(?=\n# |\Z)', re.DOTALL)
        content = pattern.sub('', content)

        # Remove stale source .env lines (path changed after upgrade/move)
        content = re.sub(r'\n?source .*?\.env\n?', '', content)

        # Remove leading/trailing blank lines left by the removal
        content = re.sub(r'\n{3,}', '\n\n', content)

        # Add source line if file was modified
        if content != original:
            content = content.rstrip() + '\n\n' + source_line + '\n'
            with open(filepath, 'w') as f:
                f.write(content)
