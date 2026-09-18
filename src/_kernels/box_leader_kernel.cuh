#pragma once
#include <stdint.h>

// Cycle-following box swap with no precomputed cycle table.
void launch_box_swap_leader(float* data,
                            long long outer_count,
                            long long rows,
                            long long cols,
                            long long item_size);
