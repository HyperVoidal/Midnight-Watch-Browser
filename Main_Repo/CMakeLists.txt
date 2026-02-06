cmake_minimum_required(VERSION 3.16)
project(Midnight-Engine)

# 1. Find Qt6 Core (needed for QString)
find_package(Qt6 REQUIRED COMPONENTS Core)

# 2. Create the library (SHARED creates the .so file)
add_library(MidnightCPP SHARED src/cpp-core/gatekeeper.cpp)

# 3. Link the Qt6 headers/libs to your library
target_link_libraries(MidnightCPP PRIVATE Qt6::Core)

# 4. Set the output directory to keep things clean
set_target_properties(MidnightCPP PROPERTIES LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})
