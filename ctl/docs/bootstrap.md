# bootstrap — 初始化 vcpkg 环境

## 职责

1. 下载对应平台的 `vcpkg` 二进制到仓库根目录
2. 扫描 shell config，设置/替换 `VCPKG_ROOT`、`PATH`

## 平台检测

| OS | 架构 | 下载文件名 |
|----|------|-----------|
| Linux (glibc) | amd64 | `vcpkg-glibc` |
| Linux (glibc) | arm64 | `vcpkg-glibc-arm64` |
| Linux (musl) | amd64 | `vcpkg-muslc` |
| macOS | any | `vcpkg-macos` |
| Windows | amd64 | `vcpkg.exe` |
| Windows | arm64 | `vcpkg-arm64.exe` |

musl 检测：`/etc/alpine-release` 存在则走 musl。

## 下载

```
https://github.com/koomx/vcpkg-tool/releases/download/{VERSION}/{FILENAME}
```

- 目标路径：`$VCPKG_ROOT/vcpkg`（Unix）/ `$VCPKG_ROOT/vcpkg.exe`（Windows）
- SHA256 校验：同 release 的 `SHA256SUMS`
- Unix: `chmod +x`

当前版本：见 `ctl/VERSION`（`2026-08-17`）。

## 环境变量

```
VCPKG_ROOT=<仓库根目录绝对路径>
PATH=$PATH:$VCPKG_ROOT
```

CMake 工具链：`$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake`

## 仓库根目录定位

脚本所在位置 `vcpkgctl` 的父目录即为仓库根目录。

## switch 命令

```
vcpkgctl switch ~/work/other-repo
```

1. 检查目标目录是否存在 `vcpkgctl`
2. 存在 → 调用 `target/vcpkgctl bootstrap`

## 后续动作

- 提示用户 `source .env` 或重开终端
- 确认 `vcpkg version` 可正常执行
