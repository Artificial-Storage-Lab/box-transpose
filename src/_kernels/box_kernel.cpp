#include <torch/extension.h>
#include "box_kernel.cuh"
#include "box_leader_kernel.cuh"

void py_adjacent_box_swap(torch::Tensor data,
                          torch::Tensor starts,
                          torch::Tensor lengths,
                          int64_t outer_count,
                          int64_t rows,
                          int64_t cols,
                          int64_t item_size)
{
    launch_adjacent_box_swap(data.data_ptr<float>(),
                             starts.data_ptr<int>(),
                             lengths.data_ptr<int>(),
                             (int)starts.numel(),
                             (long long)outer_count,
                             (long long)rows,
                             (long long)cols,
                             (long long)item_size);
}

void py_box_swap_leader(torch::Tensor data,
                        int64_t outer_count,
                        int64_t rows,
                        int64_t cols,
                        int64_t item_size)
{
    launch_box_swap_leader(data.data_ptr<float>(),
                           (long long)outer_count,
                           (long long)rows,
                           (long long)cols,
                           (long long)item_size);
}

PYBIND11_MODULE(TORCH_EXTENSION_NAME, m) {
    m.def("adjacent_box_swap", &py_adjacent_box_swap,
          "in-place adjacent-axis box-following transpose");
    m.def("box_swap_leader", &py_box_swap_leader,
          "same swap, cycle leaders decided on the device, no cycle table");
}
