cmake_minimum_required(VERSION 3.16)

project(prism_wp5_fluorescence LANGUAGES CXX)

find_package(Geant4 11.2 REQUIRED)
include(${Geant4_USE_FILE})

add_executable(prism_wp5 main.cc)
target_compile_features(prism_wp5 PRIVATE cxx_std_17)
target_link_libraries(prism_wp5 PRIVATE ${Geant4_LIBRARIES})

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(prism_wp5 PRIVATE -Wall -Wextra -Wpedantic)
endif()

install(TARGETS prism_wp5 RUNTIME DESTINATION bin)
