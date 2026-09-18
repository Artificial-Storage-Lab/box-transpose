// Leader-based box swap: the same cycle following as box_kernel.cu, with the
// precomputed starts[]/lengths[] arrays removed.
//
// box_kernel.cu is told where each cycle begins. Those arrays are built on the
// host by walking every position of the rows x cols matrix, which is
// Theta(D_mid) time and, worse, Theta(n_cycles) device memory -- on a square
// block every off-diagonal pair is its own 2-cycle, so the table approaches
// one entry per two elements and the "auxiliary memory is kilobytes" claim
// fails exactly where D_mid is largest.
//
// Here each thread block decides for itself whether the position it was handed
// is the leader of its cycle -- the smallest index in the orbit -- by walking
// the orbit and giving up the moment it sees anything smaller. Every cycle has
// exactly one leader, so every cycle is rotated exactly once, with no
// coordination and nothing stored. The leader formulation is the standard one
// for in-place permutation; Gustavson, Karlsson & Kagstrom (TOMS 2012) give an
// analytic construction for it, which would replace the search below.
//
// Square blocks are special-cased. The transpose of an n x n matrix is an
// involution, so every non-diagonal cell pairs with exactly one other and the
// leader test collapses to i < j: no walking, no divergence, full parallelism.
// Gustavson et al. Section 5 makes the same observation, calling their own
// leader machinery "overkill" in this case.

#include "box_leader_kernel.cuh"
#include <stdint.h>

__device__ __forceinline__ int lt_next(int p, int rows, int cols)
{
    return (p % cols) * rows + p / cols;
}

// ── square: transpose is an involution, leader test is one comparison ────────
template <typename T>
__global__ void square_swap_kernel(T* __restrict__ data,
                                   long long outer_count,
                                   int n,
                                   long long item_count)
{
    const long long total  = (long long)n * n;
    const long long work   = outer_count * total * item_count;
    const long long stride = (long long)gridDim.x * blockDim.x;

    for (long long t = (long long)blockIdx.x * blockDim.x + threadIdx.x;
         t < work; t += stride) {
        const long long lane = t % item_count;
        const long long rest = t / item_count;
        const long long p    = rest % total;
        const long long outer = rest / total;
        const int i = (int)(p / n);
        const int j = (int)(p % n);
        if (i >= j) continue;                   // j > i handles the pair; i == j is fixed

        const long long base = outer * total * item_count;
        const long long a = base + p * item_count + lane;
        const long long b = base + ((long long)j * n + i) * item_count + lane;
        const T tmp = data[a];
        data[a] = data[b];
        data[b] = tmp;
    }
}

// ── general, narrow item: one THREAD per candidate position ─────────────────
// The block-per-position form below spreads an item's D_post lanes across a
// block, which is right when D_post is wide and catastrophic when it is not:
// at D_post = 1 a 256-thread block moves one element and 255 threads sit out
// the leader test. Here each thread owns a position outright and walks its own
// lanes, so occupancy is set by the number of candidates rather than by D_post.
template <typename T>
__global__ void leader_swap_narrow_kernel(T* __restrict__ data,
                                          long long outer_count,
                                          int rows,
                                          int cols,
                                          long long item_count)
{
    const long long total       = (long long)rows * cols;
    const long long matrix_span = total * item_count;
    const long long n_ops       = outer_count * total;
    const long long stride      = (long long)gridDim.x * blockDim.x;

    for (long long op = (long long)blockIdx.x * blockDim.x + threadIdx.x;
         op < n_ops; op += stride) {
        const int p           = (int)(op % total);
        const long long outer = op / total;

        if (p == 0 || (long long)p >= total - 1) continue;
        int q = lt_next(p, rows, cols);
        if (q == p) continue;                       // fixed point
        bool lead = true;
        while (q != p) {
            if (q < p) { lead = false; break; }
            q = lt_next(q, rows, cols);
        }
        if (!lead) continue;

        const long long base = outer * matrix_span;
        for (long long lane = 0; lane < item_count; lane++) {
            T carry = data[base + (long long)p * item_count + lane];
            int r = p;
            do {
                const int next = lt_next(r, rows, cols);
                const long long addr = base + (long long)next * item_count + lane;
                const T old = data[addr];
                data[addr] = carry;
                carry = old;
                r = next;
            } while (r != p);
        }
    }
}

// ── general, wide item: one block per candidate, thread 0 runs the test ──────
template <typename T>
__global__ void leader_swap_kernel(T* __restrict__ data,
                                   long long outer_count,
                                   int rows,
                                   int cols,
                                   long long item_count)
{
    const long long total       = (long long)rows * cols;
    const long long matrix_span = total * item_count;
    const long long n_ops       = outer_count * total;
    const long long lane_stride = (long long)gridDim.y * blockDim.x;

    __shared__ int s_leader;

    for (long long op = blockIdx.x; op < n_ops; op += gridDim.x) {
        const int p           = (int)(op % total);
        const long long outer = op / total;

        if (threadIdx.x == 0) {
            int lead = 0;
            // 0 and total-1 are always fixed; a self-mapping p is a fixed
            // point and has nothing to rotate.
            if (p > 0 && (long long)p < total - 1) {
                int q = lt_next(p, rows, cols);
                if (q != p) {
                    lead = 1;
                    while (q != p) {
                        if (q < p) { lead = 0; break; }   // someone smaller leads
                        q = lt_next(q, rows, cols);
                    }
                }
            }
            s_leader = lead;
        }
        __syncthreads();

        if (s_leader) {
            const long long base = outer * matrix_span;
            for (long long lane = (long long)blockIdx.y * blockDim.x + threadIdx.x;
                 lane < item_count; lane += lane_stride) {
                T carry = data[base + (long long)p * item_count + lane];
                int q = p;
                do {
                    const int next = lt_next(q, rows, cols);
                    const long long addr = base + (long long)next * item_count + lane;
                    const T old = data[addr];
                    data[addr] = carry;
                    carry = old;
                    q = next;
                } while (q != p);
            }
        }
        __syncthreads();                        // before s_leader is rewritten
    }
}

void launch_box_swap_leader(float* data,
                            long long outer_count,
                            long long rows,
                            long long cols,
                            long long item_size)
{
    if (outer_count <= 0 || rows <= 0 || cols <= 0 || item_size <= 0) return;
    if (rows == 1 || cols == 1) return;         // identity: nothing moves

    const int BLOCK = 256;
    const long long MAX_GRID_X = (1LL << 31) - 1;
    const long long MAX_GRID_Y = 65535;
    const bool vec4 = (item_size % 4) == 0;
    const long long item_count = vec4 ? item_size / 4 : item_size;
    float4* data4 = reinterpret_cast<float4*>(data);

    if (rows == cols) {
        const long long work = outer_count * rows * cols * item_count;
        long long blocks = (work + BLOCK - 1) / BLOCK;
        if (blocks > 65535 * 8) blocks = 65535 * 8;     // grid-stride handles the rest
        if (blocks < 1) blocks = 1;
        if (vec4) {
            square_swap_kernel<float4><<<(unsigned int)blocks, BLOCK>>>(
                data4, outer_count, (int)rows, item_count);
        } else {
            square_swap_kernel<float><<<(unsigned int)blocks, BLOCK>>>(
                data, outer_count, (int)rows, item_count);
        }
        return;
    }

    // Below one block's worth of lanes there is nothing to spread across a
    // block, so each thread takes a whole position instead.
    if (item_count < BLOCK) {
        const long long n_ops = outer_count * rows * cols;
        long long blocks = (n_ops + BLOCK - 1) / BLOCK;
        if (blocks > 65535 * 8) blocks = 65535 * 8;
        if (blocks < 1) blocks = 1;
        if (vec4) {
            leader_swap_narrow_kernel<float4><<<(unsigned int)blocks, BLOCK>>>(
                data4, outer_count, (int)rows, (int)cols, item_count);
        } else {
            leader_swap_narrow_kernel<float><<<(unsigned int)blocks, BLOCK>>>(
                data, outer_count, (int)rows, (int)cols, item_count);
        }
        return;
    }

    dim3 grid;
    grid.x = (unsigned int)min(outer_count * rows * cols, MAX_GRID_X);
    grid.y = (unsigned int)min((item_count + BLOCK - 1) / BLOCK, MAX_GRID_Y);
    if (vec4) {
        leader_swap_kernel<float4><<<grid, BLOCK>>>(
            data4, outer_count, (int)rows, (int)cols, item_count);
    } else {
        leader_swap_kernel<float><<<grid, BLOCK>>>(
            data, outer_count, (int)rows, (int)cols, item_count);
    }
}
