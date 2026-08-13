import os
import subprocess
import sys


def install_binary(bin_path):
    pass


def get_shell_files():
    return []


def render_env_lines(vcpkg_root):
    return []


def set_env_vars(vcpkg_root):
    vars = [
        ('VCPKG_ROOT', vcpkg_root),
        ('VCPKG_CMAKE', os.path.join(vcpkg_root, 'scripts', 'buildsystems', 'vcpkg.cmake')),
    ]
    for name, value in vars:
        subprocess.run(['setx', name, value], capture_output=True)

    path_val = os.environ.get('PATH', '') + ';' + vcpkg_root
    subprocess.run(['setx', 'PATH', path_val], capture_output=True)
