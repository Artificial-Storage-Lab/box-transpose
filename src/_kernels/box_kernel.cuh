#pragma once
#include <stdint.h>

void launch_adjacent_box_swap(float* data,
                              const int* starts,
                              const int* lengths,
                              int n_cycles,
                              long long outer_count,
                              long long rows,
                              long long cols,
                              long long item_size);
