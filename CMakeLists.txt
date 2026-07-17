cmake_minimum_required(VERSION 3.10)

# fdkaac_version is a plain C string literal in version.h ("X.Y.Z");
# reuse it as the CMake project version too.
file(STRINGS "${CMAKE_CURRENT_SOURCE_DIR}/version.h" FDKAAC_VERSION_LINE
     REGEX "fdkaac_version[ \t]*=")
string(REGEX REPLACE ".*\"([0-9]+\\.[0-9]+\\.[0-9]+)\".*" "\\1"
       FDKAAC_VERSION "${FDKAAC_VERSION_LINE}")

project(fdkaac VERSION ${FDKAAC_VERSION} LANGUAGES C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED OFF)

include(CheckIncludeFile)
include(CheckSymbolExists)
include(CheckFunctionExists)
include(TestBigEndian)

if(WIN32)
    enable_language(RC)
endif()

# ---------------------------------------------------------------------------
# libfdk-aac: either the system package (default, via pkg-config) or built
# from source as a static library.
# ---------------------------------------------------------------------------
option(FDKAAC_BUILD_FDK_AAC
    "Fetch and build libfdk-aac from source as a static library instead of using the system package found via pkg-config"
    OFF)

if(FDKAAC_BUILD_FDK_AAC)
    # fdk-aac's own sources are C++; a C-only executable statically linking
    # it still needs the C++ runtime pulled in at final-link time, so we
    # need a C++ compiler available and must link fdkaac as C++.
    enable_language(CXX)
    include(ExternalProject)

    set(FDKAAC_FDK_AAC_GIT_REPOSITORY "https://github.com/mstorsjo/fdk-aac.git"
        CACHE STRING "Git repository libfdk-aac is fetched from when FDKAAC_BUILD_FDK_AAC is ON")
    set(FDKAAC_FDK_AAC_GIT_TAG "v2.0.3"
        CACHE STRING "Git tag/branch/commit of libfdk-aac to build when FDKAAC_BUILD_FDK_AAC is ON")

    set(FDK_AAC_PREFIX "${CMAKE_BINARY_DIR}/fdk-aac-install")
    set(FDK_AAC_INCLUDE_DIR "${FDK_AAC_PREFIX}/include")
    set(FDK_AAC_LIBRARY
        "${FDK_AAC_PREFIX}/lib/${CMAKE_STATIC_LIBRARY_PREFIX}fdk-aac${CMAKE_STATIC_LIBRARY_SUFFIX}")

    if(NOT CMAKE_BUILD_TYPE)
        set(FDK_AAC_BUILD_TYPE "Release")
    else()
        set(FDK_AAC_BUILD_TYPE "${CMAKE_BUILD_TYPE}")
    endif()

    # -DCMAKE_INSTALL_LIBDIR=lib pins the install layout so FDK_AAC_LIBRARY
    # above is right regardless of the target's usual GNUInstallDirs guess
    # (e.g. lib64, lib/<triplet>). Toolchain/compiler settings are forwarded
    # so the dependency is built with the same cross/native toolchain as
    # fdkaac itself (relevant for the mingw-cross / msys2 / macOS builds).
    set(FDKAAC_FDK_AAC_CMAKE_ARGS
        -DCMAKE_INSTALL_PREFIX=${FDK_AAC_PREFIX}
        -DCMAKE_INSTALL_LIBDIR=lib
        -DBUILD_SHARED_LIBS=OFF
        -DBUILD_PROGRAMS=OFF
        -DCMAKE_POSITION_INDEPENDENT_CODE=ON
        -DCMAKE_BUILD_TYPE=${FDK_AAC_BUILD_TYPE}
    )
    if(CMAKE_TOOLCHAIN_FILE)
        list(APPEND FDKAAC_FDK_AAC_CMAKE_ARGS -DCMAKE_TOOLCHAIN_FILE=${CMAKE_TOOLCHAIN_FILE})
    endif()
    if(CMAKE_C_COMPILER)
        list(APPEND FDKAAC_FDK_AAC_CMAKE_ARGS -DCMAKE_C_COMPILER=${CMAKE_C_COMPILER})
    endif()
    if(CMAKE_CXX_COMPILER)
        list(APPEND FDKAAC_FDK_AAC_CMAKE_ARGS -DCMAKE_CXX_COMPILER=${CMAKE_CXX_COMPILER})
    endif()
    if(APPLE AND CMAKE_OSX_ARCHITECTURES)
        list(APPEND FDKAAC_FDK_AAC_CMAKE_ARGS -DCMAKE_OSX_ARCHITECTURES=${CMAKE_OSX_ARCHITECTURES})
    endif()
    if(APPLE AND CMAKE_OSX_DEPLOYMENT_TARGET)
        list(APPEND FDKAAC_FDK_AAC_CMAKE_ARGS -DCMAKE_OSX_DEPLOYMENT_TARGET=${CMAKE_OSX_DEPLOYMENT_TARGET})
    endif()

    ExternalProject_Add(fdk-aac-external
        GIT_REPOSITORY   "${FDKAAC_FDK_AAC_GIT_REPOSITORY}"
        GIT_TAG          "${FDKAAC_FDK_AAC_GIT_TAG}"
        GIT_SHALLOW      TRUE
        PREFIX           "${CMAKE_BINARY_DIR}/fdk-aac-external"
        CMAKE_ARGS       ${FDKAAC_FDK_AAC_CMAKE_ARGS}
        BUILD_BYPRODUCTS "${FDK_AAC_LIBRARY}"
        INSTALL_DIR      "${FDK_AAC_PREFIX}"
    )

    # Headers don't exist yet at configure time (ExternalProject builds at
    # build time); target_include_directories just needs the path to exist
    # once the compile step actually runs, which add_dependencies below
    # guarantees.
    file(MAKE_DIRECTORY "${FDK_AAC_INCLUDE_DIR}")

    add_library(fdk-aac-static STATIC IMPORTED GLOBAL)
    set_target_properties(fdk-aac-static PROPERTIES
        IMPORTED_LOCATION "${FDK_AAC_LIBRARY}"
        INTERFACE_INCLUDE_DIRECTORIES "${FDK_AAC_INCLUDE_DIR}"
    )

    set(FDK_AAC_LINK_TARGET fdk-aac-static)
else()
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(FDK_AAC REQUIRED IMPORTED_TARGET fdk-aac)
    set(FDK_AAC_LINK_TARGET PkgConfig::FDK_AAC)
endif()

# ---------------------------------------------------------------------------
# platform / feature checks (mirrors configure.ac)
# ---------------------------------------------------------------------------
test_big_endian(WORDS_BIGENDIAN)

check_include_file("stdint.h"    HAVE_STDINT_H)
check_include_file("inttypes.h"  HAVE_INTTYPES_H)
check_include_file("unistd.h"    HAVE_UNISTD_H)
check_include_file("endian.h"    HAVE_ENDIAN_H)
check_include_file("byteswap.h"  HAVE_BYTESWAP_H)
check_include_file("libcharset.h" HAVE_LIBCHARSET_H)
check_include_file("langinfo.h"  HAVE_LANGINFO_H)

check_symbol_exists(sigaction   "signal.h" HAVE_SIGACTION)
check_symbol_exists(getopt_long "getopt.h" HAVE_GETOPT_LONG)
check_function_exists(fseeko    HAVE_FSEEKO)
check_function_exists(fseeko64  HAVE_FSEEKO64)
check_symbol_exists(_vscprintf  "stdio.h"   HAVE__VSCPRINTF)
check_symbol_exists(__timeb64   "sys/timeb.h" HAVE_STRUCT___TIMEB64)

set(ICONV_LIBRARIES)
if(NOT WIN32)
    find_package(Iconv)
    if(Iconv_FOUND)
        set(HAVE_ICONV TRUE)
        set(ICONV_LIBRARIES ${Iconv_LIBRARIES})
    endif()
    if(HAVE_LIBCHARSET_H)
        find_library(CHARSET_LIBRARY NAMES charset iconv)
        if(CHARSET_LIBRARY)
            list(APPEND ICONV_LIBRARIES ${CHARSET_LIBRARY})
        endif()
    endif()
endif()

configure_file(
    "${CMAKE_CURRENT_SOURCE_DIR}/cmake/config.h.cmake"
    "${CMAKE_CURRENT_BINARY_DIR}/config.h"
)

# ---------------------------------------------------------------------------
# sources
# ---------------------------------------------------------------------------
set(FDKAAC_SOURCES
    src/aacenc.c
    src/caf_reader.c
    src/extrapolater.c
    src/limiter.c
    src/lpc.c
    src/m4af.c
    src/main.c
    src/metadata.c
    src/parson.c
    src/pcm_float_converter.c
    src/pcm_native_converter.c
    src/pcm_readhelper.c
    src/pcm_sint16_converter.c
    src/progress.c
    src/wav_reader.c
)

if(WIN32)
    list(APPEND FDKAAC_SOURCES src/compat_win32.c fdkaac.rc)
else()
    list(APPEND FDKAAC_SOURCES src/compat_posix.c)
endif()

if(NOT HAVE_GETOPT_LONG)
    list(APPEND FDKAAC_SOURCES missings/getopt.c)
endif()

add_executable(fdkaac ${FDKAAC_SOURCES})

target_include_directories(fdkaac PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}"
    "${CMAKE_CURRENT_BINARY_DIR}"
)
if(NOT HAVE_GETOPT_LONG)
    target_include_directories(fdkaac PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/missings")
endif()

target_compile_definitions(fdkaac PRIVATE HAVE_CONFIG_H)
if(NOT WIN32)
    target_compile_definitions(fdkaac PRIVATE _FILE_OFFSET_BITS=64)
endif()

target_link_libraries(fdkaac PRIVATE ${FDK_AAC_LINK_TARGET} m ${ICONV_LIBRARIES})

if(FDKAAC_BUILD_FDK_AAC)
    add_dependencies(fdkaac fdk-aac-external)
    # fdk-aac's sources are C++; drive the final link with the C++ compiler
    # so its runtime (libstdc++/libc++) gets linked in automatically instead
    # of leaving unresolved C++ runtime symbols in a plain C link.
    set_target_properties(fdkaac PROPERTIES LINKER_LANGUAGE CXX)
endif()

install(TARGETS fdkaac RUNTIME DESTINATION bin)
install(FILES man/fdkaac.1 DESTINATION share/man/man1)
