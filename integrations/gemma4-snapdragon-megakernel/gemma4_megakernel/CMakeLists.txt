cmake_minimum_required(VERSION 3.16)

project(gemma4_megakernel LANGUAGES CXX)

option(GEMMA4_MEGAKERNEL_WARNINGS_AS_ERRORS "Treat warnings as errors" ON)

add_library(gemma4_megakernel_core STATIC
  src/core/json_writer.cpp
  src/core/sha256.cpp
  src/data/tokenizer_packer.cpp
  src/model/layer_pack_reader.cpp
  src/backends/device_probe.cpp
  src/backends/cpu_debug_backend.cpp
  src/backends/opencl_layer_runner.cpp
)

target_include_directories(gemma4_megakernel_core
  PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_compile_features(gemma4_megakernel_core PUBLIC cxx_std_17)
set_target_properties(gemma4_megakernel_core PROPERTIES CXX_EXTENSIONS OFF)

if(CMAKE_DL_LIBS)
  target_link_libraries(gemma4_megakernel_core PUBLIC ${CMAKE_DL_LIBS})
elseif(ANDROID OR CMAKE_SYSTEM_NAME STREQUAL "Linux")
  target_link_libraries(gemma4_megakernel_core PUBLIC dl)
endif()

if(MSVC)
  target_compile_options(gemma4_megakernel_core PRIVATE /W4)
  if(GEMMA4_MEGAKERNEL_WARNINGS_AS_ERRORS)
    target_compile_options(gemma4_megakernel_core PRIVATE /WX)
  endif()
else()
  target_compile_options(gemma4_megakernel_core PRIVATE -Wall -Wextra -Wpedantic)
  if(GEMMA4_MEGAKERNEL_WARNINGS_AS_ERRORS)
    target_compile_options(gemma4_megakernel_core PRIVATE -Werror)
  endif()
endif()

add_executable(gemma4_layer_runner
  src/runner/main.cpp
)

target_link_libraries(gemma4_layer_runner PRIVATE gemma4_megakernel_core)
target_compile_features(gemma4_layer_runner PRIVATE cxx_std_17)
set_target_properties(gemma4_layer_runner PROPERTIES CXX_EXTENSIONS OFF)

if(MSVC)
  target_compile_options(gemma4_layer_runner PRIVATE /W4)
  if(GEMMA4_MEGAKERNEL_WARNINGS_AS_ERRORS)
    target_compile_options(gemma4_layer_runner PRIVATE /WX)
  endif()
else()
  target_compile_options(gemma4_layer_runner PRIVATE -Wall -Wextra -Wpedantic)
  if(GEMMA4_MEGAKERNEL_WARNINGS_AS_ERRORS)
    target_compile_options(gemma4_layer_runner PRIVATE -Werror)
  endif()
endif()

enable_testing()
add_test(NAME gemma4_runner_help COMMAND gemma4_layer_runner --help)
add_test(NAME gemma4_runner_probe COMMAND gemma4_layer_runner --probe)
