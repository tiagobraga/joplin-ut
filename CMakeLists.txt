cmake_minimum_required(VERSION 3.10)
project(joplin-ut.braga VERSION 1.3.0)

set(CLICK_ARCH "all")
set(CLICK_FRAMEWORK "ubuntu-touch-24.04-1.x")

configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/manifest.json.in
    ${CMAKE_CURRENT_BINARY_DIR}/manifest.json
    @ONLY
)

configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/joplin-ut.desktop.in
    ${CMAKE_CURRENT_BINARY_DIR}/joplin-ut.desktop
    @ONLY
)

install(FILES ${CMAKE_CURRENT_BINARY_DIR}/manifest.json DESTINATION .)
install(FILES ${CMAKE_CURRENT_SOURCE_DIR}/joplin-ut.apparmor DESTINATION .)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/joplin-ut.desktop DESTINATION .)

install(DIRECTORY qml DESTINATION .)
install(DIRECTORY src DESTINATION .)
install(DIRECTORY assets DESTINATION .)
