import os
import stat


def install_binary(bin_path):
    st = os.stat(bin_path)
    os.chmod(bin_path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def get_shell_files():
    candidates = [
        '~/.bashrc',
        '~/.zshrc',
        '~/.profile',
        '~/.bash_profile',
        '~/.zprofile',
    ]
    return [os.path.expanduser(p) for p in candidates]


def render_env_lines(vcpkg_root):
    return [
        'export VCPKG_ROOT=' + vcpkg_root,
        'export PATH=$PATH:$VCPKG_ROOT',
        'export VCPKG_CMAKE=$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake',
    ]
