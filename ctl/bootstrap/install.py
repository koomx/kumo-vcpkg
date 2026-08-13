import os
import shutil
import sys

from plat import install_binary as _platform_install


def install_binary(src_path, vcpkg_root):
    dst_name = 'vcpkg.exe' if sys.platform == 'win32' else 'vcpkg'
    dst_path = os.path.join(vcpkg_root, dst_name)

    shutil.move(src_path, dst_path)
    _platform_install(dst_path)
    return dst_path
