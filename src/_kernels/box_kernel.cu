#include "box_kernel.cuh"
#include <stdint.h>

__device__ __forceinline__ int transpose_next(int p, int rows, int cols)
{
    return (p % cols) * rows + p / cols;
}

__global__ void adjacent_box_swap_scalar_kernel(
    float* __restrict__ data,
    const int* __restrict__ starts,
    const int* __restrict__ lengths,
    int n_cycles,
    long long outer_count,
    int rows,
    int cols,
    long long item_size)
{
    long long total = outer_count * n_cycles;
    long long matrix_span = (long long)rows * cols * item_size;
    long long lane_stride = (long long)gridDim.y * blockDim.x;
    for (long long outer_cycle = blockIdx.x; outer_cycle < total; outer_cycle += gridDim.x) {
        int cycle_id = (int)(outer_cycle % n_cycles);
        long long outer  = outer_cycle / n_cycles;
        long long base   = outer * matrix_span;
        int p   = starts[cycle_id];
        int len = lengths[cycle_id];
        for (long long lane = (long long)blockIdx.y * blockDim.x + threadIdx.x;
             lane < item_size; lane += lane_stride) {
            float carry = data[base + (long long)p * item_size + lane];
            int q = p;
            #pragma unroll 1
            for (int step = 0; step < len; step++) {
                int next = transpose_next(q, rows, cols);
                long long addr = base + (long long)next * item_size + lane;
                float old = data[addr];
                data[addr] = carry;
                carry = old;
                q = next;
            }
        }
    }
}

__global__ void adjacent_box_swap_float4_kernel(
    float* __restrict__ data,
    const int* __restrict__ starts,
    const int* __restrict__ lengths,
    int n_cycles,
    long long outer_count,
    int rows,
    int cols,
    long long item_size)
{
    long long item_vec4 = item_size / 4;
    long long total = outer_count * n_cycles;
    float4* data4 = reinterpret_cast<float4*>(data);
    long long matrix_span4 = (long long)rows * cols * item_vec4;
    long long lane_stride4 = (long long)gridDim.y * blockDim.x;
    for (long long outer_cycle = blockIdx.x; outer_cycle < total; outer_cycle += gridDim.x) {
        int cycle_id = (int)(outer_cycle % n_cycles);
        long long outer  = outer_cycle / n_cycles;
        long long base4  = outer * matrix_span4;
        int p   = starts[cycle_id];
        int len = lengths[cycle_id];
        for (long long lane4 = (long long)blockIdx.y * blockDim.x + threadIdx.x;
             lane4 < item_vec4; lane4 += lane_stride4) {
            float4 carry = data4[base4 + (long long)p * item_vec4 + lane4];
            int q = p;
            #pragma unroll 1
            for (int step = 0; step < len; step++) {
                int next = transpose_next(q, rows, cols);
                long long addr = base4 + (long long)next * item_vec4 + lane4;
                float4 old = data4[addr];
                data4[addr] = carry;
                carry = old;
                q = next;
            }
        }
    }
}

void launch_adjacent_box_swap(float* data,
                              const int* starts,
                              const int* lengths,
                              int n_cycles,
                              long long outer_count,
                              long long rows,
                              long long cols,
                              long long item_size)
{
    if (n_cycles == 0) return;
    const int BLOCK = 256;
    const long long MAX_GRID_X = (1LL << 31) - 1;
    const long long MAX_GRID_Y = 65535;
    dim3 grid;
    grid.x = (unsigned int)min(outer_count * (long long)n_cycles, MAX_GRID_X);
    if ((item_size % 4) == 0) {
        long long item_vec4 = item_size / 4;
        grid.y = (unsigned int)min((item_vec4 + BLOCK - 1) / BLOCK, MAX_GRID_Y);
        adjacent_box_swap_float4_kernel<<<grid, BLOCK>>>(
            data, starts, lengths, n_cycles, outer_count, (int)rows, (int)cols, item_size);
    } else {
        grid.y = (unsigned int)min((item_size + BLOCK - 1) / BLOCK, MAX_GRID_Y);
        adjacent_box_swap_scalar_kernel<<<grid, BLOCK>>>(
            data, starts, lengths, n_cycles, outer_count, (int)rows, (int)cols, item_size);
    }
}
