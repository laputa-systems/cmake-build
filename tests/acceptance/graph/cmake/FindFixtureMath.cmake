add_library(FixtureMath::FixtureMath INTERFACE IMPORTED)
set_target_properties(FixtureMath::FixtureMath PROPERTIES INTERFACE_COMPILE_DEFINITIONS MODULE_VALUE=3)
set(FixtureMath_FOUND TRUE)
