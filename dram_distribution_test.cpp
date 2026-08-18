#include <cstddef>
#include <cstdint>
#include <iostream>
#include <vector>

int main()
{
    constexpr std::size_t BYTES = 16ULL * 1024 * 1024;
    constexpr std::size_t ELEMENTS = BYTES / sizeof(std::uint64_t);

    std::vector<std::uint64_t> a(ELEMENTS, 0);

    std::uint64_t checksum = 0;

    // One access per 64-byte cache line.
    constexpr std::size_t STRIDE =
        64 / sizeof(std::uint64_t);

    for (std::size_t i = 0; i < ELEMENTS; i += STRIDE)
    {
        a[i] = static_cast<std::uint64_t>(i + 1);
    }

    for (std::size_t i = 0; i < ELEMENTS; i += STRIDE)
    {
        checksum += a[i];
    }

    std::cout << "Checksum: " << checksum << '\n';
    return 0;
}
