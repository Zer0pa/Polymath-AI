cmake_minimum_required(VERSION 3.22.1)

project(polymath_lab_native LANGUAGES CXX)

if(DEFINED ENV{POLYMATH_ZIG_EXECUTABLE} AND NOT "$ENV{POLYMATH_ZIG_EXECUTABLE}" STREQUAL "")
    set(ZIG_EXECUTABLE "$ENV{POLYMATH_ZIG_EXECUTABLE}" CACHE FILEPATH "Zig compiler executable" FORCE)
    if(NOT EXISTS "${ZIG_EXECUTABLE}")
        message(FATAL_ERROR "POLYMATH_ZIG_EXECUTABLE does not exist: ${ZIG_EXECUTABLE}")
    endif()
else()
    find_program(ZIG_EXECUTABLE zig REQUIRED)
endif()

set(PHASE1_ZIG_SOURCE
    ${CMAKE_CURRENT_LIST_DIR}/../../../../native_import/phase1_qa_stream_zig/phase1_qa_stream.zig
)
set(PHASE1_ZIG_RAW_OBJECT ${CMAKE_CURRENT_BINARY_DIR}/phase1_qa_stream_zig_raw.o)
set(PHASE1_ZIG_OBJECT ${CMAKE_CURRENT_BINARY_DIR}/phase1_qa_stream_zig.o)

if(NOT CMAKE_OBJCOPY)
    find_program(CMAKE_OBJCOPY llvm-objcopy REQUIRED)
endif()

add_custom_command(
    OUTPUT ${PHASE1_ZIG_RAW_OBJECT}
    COMMAND ${ZIG_EXECUTABLE}
            build-obj
            ${PHASE1_ZIG_SOURCE}
            -target
            aarch64-linux-android
            -OReleaseFast
            -fPIC
            -fno-lld
            -femit-bin=${PHASE1_ZIG_RAW_OBJECT}
    DEPENDS ${PHASE1_ZIG_SOURCE}
    VERBATIM
)

add_custom_command(
    OUTPUT ${PHASE1_ZIG_OBJECT}
    COMMAND ${CMAKE_OBJCOPY}
            --redefine-sym
            main=phase1_qa_stream_main
            ${PHASE1_ZIG_RAW_OBJECT}
            ${PHASE1_ZIG_OBJECT}
    DEPENDS ${PHASE1_ZIG_RAW_OBJECT}
    VERBATIM
)

set_source_files_properties(
    ${PHASE1_ZIG_OBJECT}
    PROPERTIES
    EXTERNAL_OBJECT TRUE
    GENERATED TRUE
)

add_library(
    polymath_lab_native
    SHARED
    ${PHASE1_ZIG_OBJECT}
    phase1_lab_engine.cpp
    polymath_lab_jni.cpp
)

target_compile_features(polymath_lab_native PRIVATE cxx_std_17)

target_compile_options(
    polymath_lab_native
    PRIVATE
    -Wall
    -Wextra
    -Wpedantic
)

target_include_directories(polymath_lab_native PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

find_library(log-lib log)
target_link_libraries(polymath_lab_native PRIVATE ${log-lib})
