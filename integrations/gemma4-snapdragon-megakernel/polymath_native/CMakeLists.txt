cmake_minimum_required(VERSION 3.20)

project(polymath_native LANGUAGES CXX)

option(POLYMATH_NATIVE_WARNINGS_AS_ERRORS "Treat native lab compiler warnings as errors" ON)
option(POLYMATH_NATIVE_ENABLE_OPENCL "Build the experimental OpenCL backend" OFF)
option(POLYMATH_NATIVE_ENABLE_VULKAN "Build the experimental Vulkan backend" OFF)

if(POLYMATH_NATIVE_ENABLE_OPENCL)
  message(FATAL_ERROR "OpenCL backend is a skeleton only; keep this disabled until correctness tests exist.")
endif()

if(POLYMATH_NATIVE_ENABLE_VULKAN)
  message(FATAL_ERROR "Vulkan backend is a skeleton only; keep this disabled until correctness tests exist.")
endif()

add_library(polymath_native_cpu STATIC
  src/cpu_kernels.cpp
)

target_include_directories(polymath_native_cpu
  PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_compile_features(polymath_native_cpu PUBLIC cxx_std_17)

if(MSVC)
  target_compile_options(polymath_native_cpu PRIVATE /W4)
  if(POLYMATH_NATIVE_WARNINGS_AS_ERRORS)
    target_compile_options(polymath_native_cpu PRIVATE /WX)
  endif()
else()
  target_compile_options(polymath_native_cpu PRIVATE -Wall -Wextra -Wpedantic)
  if(POLYMATH_NATIVE_WARNINGS_AS_ERRORS)
    target_compile_options(polymath_native_cpu PRIVATE -Werror)
  endif()
endif()

add_executable(native_kernel_tests
  tests/native_kernel_tests.cpp
)

target_link_libraries(native_kernel_tests PRIVATE polymath_native_cpu)
target_compile_features(native_kernel_tests PRIVATE cxx_std_17)

if(MSVC)
  target_compile_options(native_kernel_tests PRIVATE /W4)
  if(POLYMATH_NATIVE_WARNINGS_AS_ERRORS)
    target_compile_options(native_kernel_tests PRIVATE /WX)
  endif()
else()
  target_compile_options(native_kernel_tests PRIVATE -Wall -Wextra -Wpedantic)
  if(POLYMATH_NATIVE_WARNINGS_AS_ERRORS)
    target_compile_options(native_kernel_tests PRIVATE -Werror)
  endif()
endif()

enable_testing()
add_test(NAME native_kernel_tests_json COMMAND native_kernel_tests)
