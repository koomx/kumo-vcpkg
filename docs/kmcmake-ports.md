# kmcmake 项目：打本仓 vcpkg port

凡是 `vcpkgctl gencmake` / [koomx/kmcmake](https://github.com/koomx/kmcmake) 生成的工程，CMake 安装布局和开关都一样。registry 侧**复制** [`ports/turbo`](../ports/turbo) 改名字和依赖即可，不要每个项目重新设计 portfile。

函数名全部是 `vcpkg_*`。不要写 `kmpkg_*` / `kmpkg.json` / `kmpkg-cmake`。

通用硬约束见 [AI.md](AI.md)（只动当前 `ports/<name>/`，不手改 `versions/`、`baseline`、`port-version`）。

## 便利边界

复制 turbo 就能覆盖：

- `vcpkg_cmake_*` 安装
- `CONFIG_PATH lib/cmake/<name>`
- pkg-config
- 静态库 alias
- 关闭 test / benchmark / examples / CPM

需要额外改的：

- `cmake/*_deps.cmake` 里真正 `find_package` 的运行时 port（turbo 没有第三方运行时依赖）
- 上游确实 `install` 了可执行文件才 `vcpkg_copy_tools`
- `HEAD_REF` 不是 `main` 时改成上游默认分支

## 配方（以 turbo 为模板）

三件套：`ports/<name>/vcpkg.json`、`portfile.cmake`、`usage`。

### `vcpkg.json`

- `name` = `ports/<name>/` 目录名 = CMake `project()` = `PACKAGE_NAME`
- `version` **只跟 git tag**（`v0.7.9` → `"0.7.9"`）。忽略 CMakeLists 里的 `PROJECT_VERSION`
- host **必须**有 `vcpkg-cmake` 和 `vcpkg-cmake-config`
- `dependencies` 只列运行时 `find_package` 的库。不要为了关着的测试去列 `gtest` / `benchmark`

```json
{
  "name": "turbo",
  "version": "0.7.9",
  "description": ["Turbo kumo search fundamental cpp library."],
  "homepage": "https://github.com/koomx/turbo",
  "license": "Apache-2.0",
  "dependencies": [
    { "name": "vcpkg-cmake", "host": true },
    { "name": "vcpkg-cmake-config", "host": true }
  ]
}
```

### `portfile.cmake`

```cmake
if(NOT VCPKG_TARGET_IS_WINDOWS)
    vcpkg_check_linkage(ONLY_STATIC_LIBRARY)
endif()

vcpkg_from_github(
    OUT_SOURCE_PATH SOURCE_PATH
    REPO koomx/turbo
    REF v${VERSION}
    SHA512 <fill-after-first-overlay-install>
    HEAD_REF main
)

vcpkg_cmake_configure(
    SOURCE_PATH "${SOURCE_PATH}"
    DISABLE_PARALLEL_CONFIGURE
    OPTIONS
        -DKMCMAKE_BUILD_TEST=OFF
        -DKMCMAKE_BUILD_BENCHMARK=OFF
        -DKMCMAKE_BUILD_EXAMPLES=OFF
        -DKMCMAKE_USE_CPM=OFF
)

vcpkg_cmake_install()
vcpkg_cmake_config_fixup(PACKAGE_NAME turbo CONFIG_PATH lib/cmake/turbo)
vcpkg_fixup_pkgconfig()
vcpkg_copy_pdbs()

file(REMOVE_RECURSE "${CURRENT_PACKAGES_DIR}/debug/include")
file(REMOVE_RECURSE "${CURRENT_PACKAGES_DIR}/debug/share")

file(INSTALL "${CMAKE_CURRENT_LIST_DIR}/usage" DESTINATION "${CURRENT_PACKAGES_DIR}/share/${PORT}")
vcpkg_install_copyright(FILE_LIST "${SOURCE_PATH}/LICENSE")
```

改：`REPO`、`HEAD_REF`、`PACKAGE_NAME` / `CONFIG_PATH`、`SHA512`。`REF` 固定 `v${VERSION}`。

`-DKMCMAKE_USE_CPM=OFF` 必带：不少项目 `*_user_option.cmake` 默认 CPM=ON，不关会绕过 vcpkg。

库 port 不要 `copy_tools`。有已安装工具再加 `vcpkg_copy_tools(TOOL_NAMES … AUTO_CLEAN)`。

### `usage`

kmcmake `kmcmake_cc_library(NAME turbo)` 导出的静态目标是 **`turbo::turbo_static`**，不是 `turbo::turbo`。

```
turbo provides CMake targets:

    find_package(turbo CONFIG REQUIRED)
    target_link_libraries(main PRIVATE turbo::turbo_static)
```

必须 `file(INSTALL … usage)`，否则 post-build 会警告 usage 没装进 `share/<port>/`。

## 新增：overlay 试装再 publish

不要在本仓跑 `vcpkgctl bootstrap`。用系统已有的 `vcpkg`（`VCPKG_ROOT` 指向系统安装）。跑 portfile 的 CMake 需要支持 `string(JSON … STRING_ENCODE)`（CMake 4.4+）。

```bash
# 1. 复制 ports/turbo → ports/<name>，改 name / REPO / 依赖 / usage 目标名
# 2. SHA512 可先占位
# 3. 第一次 overlay：日志里的 Actual SHA512 填回 portfile.cmake
vcpkg install <name> --overlay-ports="$(pwd)/ports/<name>"

# 4. 再装应成功
vcpkg install <name> --overlay-ports="$(pwd)/ports/<name>"

# 5. 写入 versions/ + baseline 并 commit（会 git commit，push 另说）
vcpkgctl publish -o . <name>
```

跳过试装不要 publish。

## 升级

上游打了新 tag 之后，本仓只跟 tag。`REF v${VERSION}` 不用改。

```bash
# 0. git ls-remote --tags … 确认 tag；v0.8.0 → json 写成 "0.8.0"
# 1. 只改 ports/<name>/vcpkg.json 的 version（新运行时依赖才改 dependencies）
vcpkg remove <name> --recurse
vcpkg install <name> --overlay-ports="$(pwd)/ports/<name>"   # 抄新 SHA512
vcpkg install <name> --overlay-ports="$(pwd)/ports/<name>"
vcpkgctl publish -o . <name>
```

不要动：`REPO`、`HEAD_REF`、那组 `KMCMAKE_*=OFF`、`CONFIG_PATH`（除非上游安装布局变了）。不要为了升版本去改别的 port。
