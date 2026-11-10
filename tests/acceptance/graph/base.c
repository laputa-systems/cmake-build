#include "graph.h"
#ifndef IMPORTED_VALUE
#error imported definition missing
#endif
int base(void) { return IMPORTED_VALUE + MODULE_VALUE + generated(); }
