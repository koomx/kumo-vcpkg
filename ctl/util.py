import os


def vcpkg_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
