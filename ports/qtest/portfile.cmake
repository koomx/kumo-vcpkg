if(NOT VCPKG_TARGET_IS_WINDOWS)
    vcpkg_check_linkage(ONLY_STATIC_LIBRARY)
endif()

vcpkg_from_github(
    OUT_SOURCE_PATH SOURCE_PATH
    REPO koomx/qtest
    REF v${VERSION}
    SHA512 15d7a225fd8bb1ef3b7e7f2e673930c3b98c4d6ad788d7a014726dcf8abf3374d865e35fc8329fad61fe1c500fd53c068196d782d8c86eace7c034ca63658690
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
vcpkg_cmake_config_fixup(PACKAGE_NAME qtest CONFIG_PATH lib/cmake/qtest)
vcpkg_fixup_pkgconfig()
vcpkg_copy_pdbs()

file(REMOVE_RECURSE "${CURRENT_PACKAGES_DIR}/debug/include")
file(REMOVE_RECURSE "${CURRENT_PACKAGES_DIR}/debug/share")

file(INSTALL "${CMAKE_CURRENT_LIST_DIR}/usage" DESTINATION "${CURRENT_PACKAGES_DIR}/share/${PORT}")
vcpkg_install_copyright(FILE_LIST "${SOURCE_PATH}/LICENSE")
