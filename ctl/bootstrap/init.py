import os


def prepare_root(vcpkg_root):
    marker = os.path.join(vcpkg_root, '.vcpkg-root')
    if not os.path.isfile(marker):
        open(marker, 'w').close()
