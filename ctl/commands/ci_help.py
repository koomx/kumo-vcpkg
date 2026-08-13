"""Show CI configuration reference for all supported platforms"""
COMMAND_NAME = 'ci-help'


def setup(subparser):
    subparser.set_defaults(func=run)


def run(args):
    print(_REFERENCE)


_REFERENCE = """
vcpkg CI Reference
==================

Platforms
---------

linux-glibc (amd64):
  runs-on: ubuntu-latest
  packages: git python3
  bootstrap: python3 vcpkgctl bootstrap
  test: ./vcpkg install <pkgs>
  note: cmake/ninja bootstrapped automatically if missing

linux-musl (amd64):
  runs-on: ubuntu-latest
  container: alpine:3.20
  packages: python3 git build-base
  bootstrap: python3 vcpkgctl bootstrap
  test: ./vcpkg install <pkgs>
  note: cmake via pip (musl wheel), ninja via apk

linux-arm64:
  runs-on: ubuntu-24.04-arm
  packages: git python3
  bootstrap: python3 vcpkgctl bootstrap
  test: ./vcpkg install <pkgs>

linux-centos / rhel:
  runs-on: ubuntu-latest
  container: quay.io/centos/centos:stream9
  packages: python3 git cmake gcc-c++ ninja-build
  setup: dnf install -y epel-release && /usr/bin/crb enable
  bootstrap: python3 vcpkgctl bootstrap
  test: ./vcpkg install <pkgs>

macos (arm64):
  runs-on: macos-latest
  packages: git python3
  bootstrap: python3 vcpkgctl bootstrap
  test: ./vcpkg install <pkgs>

windows (amd64):
  runs-on: windows-latest
  packages: git python3 (>= 3.8)
  bootstrap: python vcpkgctl bootstrap
  test: ./vcpkg --debug install <pkgs>
  env: VCPKG_KEEP_ENV_VARS=PATH

windows (arm64):
  note: download vcpkg-arm64.exe from koomx/vcpkg-tool, or build from source


Quick Start
-----------

  1. Create a CI workflow (.github/workflows/ci.yml):

     on: [push, pull_request]
     jobs:
       test:
         runs-on: ubuntu-latest
         steps:
           - uses: actions/checkout@v4
           - run: python3 vcpkgctl bootstrap --disable-metrics
           - run: ./vcpkg version
           - run: ./vcpkg install <your-packages>

  2. The bootstrap step handles cmake (>= 3.31.10), ninja, and make
     automatically across all platforms.

  3. For local development: python3 vcpkgctl bootstrap

"""  # noqa: W293
