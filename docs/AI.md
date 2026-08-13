# vcpkgctl 仓库：给 AI 的操作手册

本仓是 **标准 vcpkg 格式** 的自定义 registry（`vcpkg.json` + `portfile.cmake` + `versions/`），入口是根目录 `vcpkgctl`。二进制是 `vcpkg`。不要写 `kmpkg` / `kmpkg.json` / `kmpkg_*`。

写业务代码选库时，先看本仓 `ports/` 里已有配方。

## 硬约束

- 只改当前目标 `ports/<name>/`。新增或升级某个 port 时，**不得修改任意其他 port**，除非用户点名。
- 不要手改 `versions/` 里的 `git-tree`、不要手改 `baseline.json` 的 baseline；这些由 `vcpkgctl publish` 写。
- 不要在 `vcpkg.json` 里手写 `port-version` 自增。
- 不要改 `registry.txt`。不要删 `.vcpkg-root`。
- `ports/vcpkg-*`（`vcpkg-cmake`、`vcpkg-cmake-config` 等）是构建系统内建 port，不要删。
- 所有 CMake port（含零第三方依赖的 kmcmake 项目）在 `vcpkg.json` 里 **必须** host 依赖 `vcpkg-cmake` + `vcpkg-cmake-config`。缺了会报 `Unknown CMake command "vcpkg_cmake_configure"`。

发布顺序：改 port → overlay 试装通过 → `vcpkgctl publish -o . <name>`（会 commit）→ `git push`。不要跳过试装直接 publish。

---

## 一、Merge / clone port（从别的 vcpkg 仓并入）

源和目标都必须是 **已经是 git 仓库的标准 vcpkg 仓**（有 `ports/<name>/vcpkg.json`）。源仓要干净（无未提交改动）。

```bash
# 单个（会递归带上 dependencies 里尚未存在于目标的 port）
vcpkgctl import -i /path/to/source-vcpkg -o /path/to/this-repo fmt

# 多个
vcpkgctl import -i /path/to/source-vcpkg -o /path/to/this-repo fmt spdlog

# 全部
vcpkgctl import -i /path/to/source-vcpkg -o /path/to/this-repo --all
```

行为：

- 按 `vcpkg.json` 识别 port，**原样 copytree**，不做名字改写。
- 目标里已有的 `ports/<name>` 会 skip。
- 同步拷 `versions/` 条目和 `baseline.json`，然后在 **目标仓** git commit（operator: vcpkgctl）。
- 没有 `--vcpkg` / `--kmpkg`。旧 kmpkg 仓不要当源。

「clone 一个 port」= 把源仓 clone 到本地后对这个仓库跑 `import`，不要手拷再手改 `versions/`。

---

## 二、新增普通 port

配方两件套：`ports/<name>/vcpkg.json`、`ports/<name>/portfile.cmake`。只动这一个目录。

```bash
# 1. 写 vcpkg.json：name / version / description / homepage / license / dependencies
#    CMake 构建必须带 host: vcpkg-cmake、vcpkg-cmake-config
#
# 2. 写 portfile.cmake：vcpkg_from_github + vcpkg_cmake_configure / install / config_fixup
#    SHA512 可先占位（抄个别的 port 的值）
#
# 3. overlay 试装，第一次会因 SHA 失败，日志里的 Actual SHA512 填回去
./vcpkg install <name> --overlay-ports="$(pwd)/ports/<name>"
#
# 4. 再装一次应成功
./vcpkg install <name> --overlay-ports="$(pwd)/ports/<name>"
#
# 5. 写入 versions/ + commit
vcpkgctl publish -o . <name>
git push
```

---

## 三、更新普通 port

只动 `ports/<name>/`。`portfile.cmake` 里 `REF` 若已是 `"${VERSION}"` 或 `v${VERSION}`，一般只改 json 的 version + SHA512。

```bash
# 1. 改 ports/<name>/vcpkg.json 的 version（git tag / 上游发布号）
#    依赖有变才改 dependencies，不要顺手改别的 port
#
# 2. 清掉已装的旧包，避免缓存挡着新 tarball
./vcpkg remove <name> --recurse
#
# 3. overlay 试装：旧 SHA512 对不上新包，日志里抄 Actual SHA512
./vcpkg install <name> --overlay-ports="$(pwd)/ports/<name>"
#
# 4. 把 portfile.cmake 的 SHA512 换成真实值，再装一次应成功
./vcpkg install <name> --overlay-ports="$(pwd)/ports/<name>"
#
# 5. publish 会写 versions/ + baseline 并 commit
vcpkgctl publish -o . <name>
git push
```

配方修 bug、不升上游版本时：只改 `portfile.cmake`（或补 patch），同样 overlay 验证后 `publish`（不要手改 port-version）。

---

## 四、新增 kmcmake 项目的 port

kmcmake 仓库用 `vcpkgctl gencmake <name> -o <dir>` 生成（模板 `https://github.com/koomx/kmcmake.git`）。打成 registry port 时，照 xlog 这一套，函数名全部是 `vcpkg_*`。

参考（旧仓写法，移植时把 `kmpkg_*` → `vcpkg_*`，`kmpkg-cmake` → `vcpkg-cmake`）：

- `../rdonly-kmpkg/kmpkgcore/ports/xlog/kmpkg.json`
- `../rdonly-kmpkg/kmpkgcore/ports/xlog/portfile.cmake`

### `ports/<name>/vcpkg.json`

```json
{
  "name": "xlog",
  "version": "0.5.0",
  "description": ["A command line log."],
  "homepage": "https://github.com/koomx/xlog",
  "license": "Apache-2.0",
  "dependencies": [
    { "name": "vcpkg-cmake", "host": true },
    { "name": "vcpkg-cmake-config", "host": true },
    "fmt"
  ]
}
```

- `version` 对齐上游 **git tag**（`v0.5.0` → `"0.5.0"`），不要看 CMakeLists 里的 PROJECT_VERSION。
- 运行时依赖按项目 `vcpkg.json` / CMake 实际链接来写（xlog 有 `fmt`）。
- 不要漏两个 host cmake helper。

### `ports/<name>/portfile.cmake`

```cmake
if(NOT VCPKG_TARGET_IS_WINDOWS)
    vcpkg_check_linkage(ONLY_STATIC_LIBRARY)
endif()

vcpkg_from_github(
    OUT_SOURCE_PATH SOURCE_PATH
    REPO koomx/xlog
    REF v${VERSION}
    SHA512 <fill-after-first-overlay-install>
    HEAD_REF master
)

vcpkg_cmake_configure(
    SOURCE_PATH "${SOURCE_PATH}"
    DISABLE_PARALLEL_CONFIGURE
    OPTIONS
        -DKMCMAKE_BUILD_TEST=OFF
)

vcpkg_cmake_install()
vcpkg_cmake_config_fixup(PACKAGE_NAME xlog CONFIG_PATH lib/cmake/xlog)
vcpkg_fixup_pkgconfig()
vcpkg_copy_pdbs()

file(REMOVE_RECURSE "${CURRENT_PACKAGES_DIR}/debug/include")
file(REMOVE_RECURSE "${CURRENT_PACKAGES_DIR}/debug/share")

vcpkg_install_copyright(FILE_LIST "${SOURCE_PATH}/LICENSE")
```

改这三个：`REPO`、`PACKAGE_NAME` / `CONFIG_PATH`（一般是 `lib/cmake/<name>`）、`SHA512`。`REF` 固定 `v${VERSION}`。关闭测试用 `-DKMCMAKE_BUILD_TEST=OFF`。

然后同一套 overlay 试装 → 填 SHA512 → 再装 → `vcpkgctl publish -o . <name>` → `git push`。

---

## 五、更新 kmcmake port

上游打了新 tag 之后，本仓只跟 tag，不跟 CMakeLists 的 PROJECT_VERSION。`REF v${VERSION}` 不用改，改 version 就会拉新 tarball。

```bash
# 0. 确认上游 tag：git ls-remote --tags https://github.com/<org>/<repo>.git
#    v0.6.0 → vcpkg.json 写成 "0.6.0"
#
# 1. 只改 ports/<name>/vcpkg.json 的 version
#    新增运行时依赖才改 dependencies；host 的 vcpkg-cmake / vcpkg-cmake-config 保持
#
# 2. 清缓存
./vcpkg remove <name> --recurse
#
# 3. overlay 失败 → 把 Actual SHA512 写进 portfile.cmake
./vcpkg install <name> --overlay-ports="$(pwd)/ports/<name>"
#
# 4. 再装应出现 All requested installations completed successfully
./vcpkg install <name> --overlay-ports="$(pwd)/ports/<name>"
#
# 5. 发布
vcpkgctl publish -o . <name>
git push
```

不要动：`REPO`、`HEAD_REF`、`-DKMCMAKE_BUILD_TEST=OFF`、`CONFIG_PATH`（除非上游安装布局变了）。不要为了升版本去改别的 port。

---

## 六、常用命令

先在本仓库根目录：`python3 vcpkgctl bootstrap --disable-metrics`，再 `source .env`。

| 命令 | 做什么 |
|------|--------|
| `vcpkgctl import -i <src> -o <dst> [ports…]` | merge / clone port |
| `vcpkgctl import -i <src> -o <dst> --all` | 并入源仓全部 port |
| `vcpkgctl publish -o . <port…>` | 更新 baseline/versions 并 commit |
| `vcpkgctl pull` | `git pull` |
| `vcpkgctl push` | `git push` |
| `vcpkgctl sync` | 更新工程里 `vcpkg-configuration.json` 的 git baseline |
| `vcpkgctl gencmake <name> -o <dir>` | 从 koomx/kmcmake 生成 C++ 工程（目录必须已存在且没有 CMakeLists） |
| `vcpkgctl new <dir> -r <url>` | 建一个新的 vcpkg 格式 registry 仓 |
| `vcpkgctl switch <dir>` | 切到另一个已有 `vcpkgctl` 的仓并 bootstrap |
| `vcpkgctl upgrade [--force]` | 升级 vcpkgctl + vcpkg 二进制 |

`gencmake` 之后：在输出目录 `git init && git tag v0.1.0`。版本以 tag 为准。进本 registry 按第四节加 port，升 tag 按第五节改 version + SHA512。
