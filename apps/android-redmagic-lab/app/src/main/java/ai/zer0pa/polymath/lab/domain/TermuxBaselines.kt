package ai.zer0pa.polymath.lab.domain

data class TermuxBaseline(
    val scale: String,
    val variant: String,
    val records: Long,
    val tokenIds: Long,
    val tokenIdsPerSec: Double,
    val recordsPerSec: Double,
    val materialHash: String
)

object TermuxBaselines {
    val phase1Selected = listOf(
        TermuxBaseline(
            scale = "10k",
            variant = "tenk_heap_dyn_c512_trial2",
            records = 10_000,
            tokenIds = 242_340,
            tokenIdsPerSec = 16_402_897.6177,
            recordsPerSec = 676_854.7337,
            materialHash = "c13b0ce3ee132871ca59d6d580965dfad56108a057456542e8db33be7bb9a652"
        ),
        TermuxBaseline(
            scale = "100k",
            variant = "hundredk_heap_static_bg8_trial2",
            records = 100_000,
            tokenIds = 2_616_577,
            tokenIdsPerSec = 49_068_772.5901,
            recordsPerSec = 1_875_303.9788,
            materialHash = "f9647ebfc3261e236ad66edd4379272379e2fb25ede64248965b0bf08185f38e"
        ),
        TermuxBaseline(
            scale = "1M",
            variant = "million_heap_dyn_c8192_trial0",
            records = 1_000_000,
            tokenIds = 28_161_180,
            tokenIdsPerSec = 62_634_625.4288,
            recordsPerSec = 2_224_147.7605,
            materialHash = "9fe1b93ddb5f6485eadaf784a42943419b7dc6a6161fc9d7509e29061efada08"
        )
    )
}
