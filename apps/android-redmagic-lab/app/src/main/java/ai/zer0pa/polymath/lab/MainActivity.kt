package ai.zer0pa.polymath.lab

import android.content.Intent
import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import ai.zer0pa.polymath.lab.data.newUtcRunId
import ai.zer0pa.polymath.lab.domain.Phase1RunRequest
import ai.zer0pa.polymath.lab.domain.SourceMode
import ai.zer0pa.polymath.lab.ui.PolymathLabApp
import kotlinx.coroutines.runBlocking

class MainActivity : ComponentActivity() {
    private lateinit var container: LabAppContainer

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        container = LabAppContainer(this)
        setContent {
            PolymathLabApp(container = container)
        }
        handleIntent(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleIntent(intent)
    }

    override fun onResume() {
        super.onResume()
        val mode = container.gameAuthorityController.currentGameMode()
        Log.i(TAG, "resume package=ai.zer0pa.polymath.lab game_mode=${mode.modeName}")
    }

    override fun onPause() {
        container.gameAuthorityController.setBenchmarkActive(false)
        super.onPause()
    }

    private fun handleIntent(intent: Intent?) {
        if (intent?.action == ACTION_SET_BENCHMARK_STATE) {
            val active = intent.getBooleanExtra(EXTRA_ACTIVE, false)
            container.gameAuthorityController.setLoading(false)
            container.gameAuthorityController.setBenchmarkActive(active)
            Log.i(TAG, "adb_benchmark_state active=$active")
            return
        }
        if (intent?.action != ACTION_WRITE_PROBE_REPORT) {
            return
        }
        Thread {
            val runId = newUtcRunId()
            Log.i(TAG, "adb_probe_report_requested run_id=${runId.value}")
            val result = runBlocking {
                container.phase1TokenizerEngine.runTokenizer(
                    Phase1RunRequest(
                        runId = runId,
                        sourceMode = SourceMode.MEGASCIENCE,
                        requestedRecords = null,
                        tokenizerDir = intent.getStringExtra(EXTRA_TOKENIZER_DIR),
                        gbt1Path = intent.getStringExtra(EXTRA_GBT1_PATH),
                        batchListPath = intent.getStringExtra(EXTRA_BATCH_LIST_PATH),
                        qai1Path = intent.getStringExtra(EXTRA_QAI1_PATH),
                        bpeAlgorithm = intent.getStringExtra(EXTRA_BPE_ALGORITHM) ?: "heap",
                        workerCount = intent.getIntExtra(EXTRA_WORKER_COUNT, 1),
                        batchHint = 0,
                        phase1ExecPath = intent.getStringExtra(EXTRA_PHASE1_EXEC_PATH),
                        flags = intent.getIntExtra(EXTRA_FLAGS, 0)
                    )
                )
            }
            Log.i(TAG, "adb_probe_report_written run_id=${runId.value} root=${result.reportRoot.deviceRelativePath}")
        }.start()
    }

    private companion object {
        const val ACTION_WRITE_PROBE_REPORT = "ai.zer0pa.polymath.lab.WRITE_PROBE_REPORT"
        const val ACTION_SET_BENCHMARK_STATE = "ai.zer0pa.polymath.lab.SET_BENCHMARK_STATE"
        const val EXTRA_ACTIVE = "active"
        const val EXTRA_TOKENIZER_DIR = "tokenizer_dir"
        const val EXTRA_GBT1_PATH = "gbt1_path"
        const val EXTRA_BATCH_LIST_PATH = "batch_list_path"
        const val EXTRA_QAI1_PATH = "qai1_path"
        const val EXTRA_BPE_ALGORITHM = "bpe_algorithm"
        const val EXTRA_WORKER_COUNT = "worker_count"
        const val EXTRA_PHASE1_EXEC_PATH = "phase1_exec_path"
        const val EXTRA_FLAGS = "flags"
        const val TAG = "PolymathLabActivity"
    }
}
