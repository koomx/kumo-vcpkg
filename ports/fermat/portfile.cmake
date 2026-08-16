if(NOT VCPKG_TARGET_IS_WINDOWS)
    vcpkg_check_linkage(ONLY_STATIC_LIBRARY)
endif()

vcpkg_from_github(
    OUT_SOURCE_PATH SOURCE_PATH
    REPO koomx/fermat
    REF v${VERSION}
    SHA512 9734aa3926c9ffacc11840b3f2f17c8fb58b04b76b4ff04195eb3c2d0570ce19ec49d1901baf660e3b95e7c8b347f61979bbc1505e7db58550eb2361215aa6b1
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
vcpkg_cmake_config_fixup(PACKAGE_NAME fermat CONFIG_PATH lib/cmake/fermat)
vcpkg_fixup_pkgconfig()
vcpkg_copy_pdbs()

file(REMOVE_RECURSE "${CURRENT_PACKAGES_DIR}/debug/include")
file(REMOVE_RECURSE "${CURRENT_PACKAGES_DIR}/debug/share")

file(INSTALL "${CMAKE_CURRENT_LIST_DIR}/usage" DESTINATION "${CURRENT_PACKAGES_DIR}/share/${PORT}")
vcpkg_install_copyright(FILE_LIST "${SOURCE_PATH}/LICENSE")
