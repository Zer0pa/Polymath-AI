package ai.zer0pa.polymath.lab.data

import android.app.Activity
import android.app.GameManager
import android.app.GameState
import android.os.Build
import android.os.Looper
import android.util.Log
import android.view.WindowManager
import ai.zer0pa.polymath.lab.domain.GameAuthorityController
import ai.zer0pa.polymath.lab.domain.GameModeSnapshot
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

class AndroidGameAuthorityController(private val activity: Activity) : GameAuthorityController {
    override fun currentGameMode(): GameModeSnapshot {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) {
            return GameModeSnapshot(
                apiLevel = Build.VERSION.SDK_INT,
                modeCode = null,
                modeName = "API_BELOW_GAME_MODE",
                supported = false,
                message = "GameManager requires Android 12/API 31 or newer."
            )
        }

        val manager = activity.getSystemService(GameManager::class.java)
        val mode = manager?.gameMode
        val snapshot = GameModeSnapshot(
            apiLevel = Build.VERSION.SDK_INT,
            modeCode = mode,
            modeName = gameModeName(mode),
            supported = mode != null && mode != GameManager.GAME_MODE_UNSUPPORTED,
            message = "Queried GameManager.getGameMode on resume path."
        )
        Log.i(TAG, "game_mode_query mode=${snapshot.modeName} api=${snapshot.apiLevel}")
        return snapshot
    }

    override fun setLoading(isLoading: Boolean) {
        runOnUiThreadBlocking {
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
                Log.i(TAG, "game_state_loading skipped api=${Build.VERSION.SDK_INT}")
                return@runOnUiThreadBlocking
            }
            val mode = if (isLoading) GameState.MODE_CONTENT else GameState.MODE_NONE
            activity.getSystemService(GameManager::class.java)?.setGameState(GameState(isLoading, mode))
            Log.i(TAG, "game_state_loading is_loading=$isLoading mode=$mode")
        }
    }

    override fun setBenchmarkActive(active: Boolean) {
        runOnUiThreadBlocking {
            if (active) {
                activity.window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            } else {
                activity.window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            }

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                val mode = if (active) {
                    GameState.MODE_GAMEPLAY_UNINTERRUPTIBLE
                } else {
                    GameState.MODE_NONE
                }
                activity.getSystemService(GameManager::class.java)?.setGameState(GameState(false, mode))
                Log.i(TAG, "game_state_benchmark active=$active mode=$mode")
            } else {
                Log.i(TAG, "game_state_benchmark active=$active api=${Build.VERSION.SDK_INT}")
            }
        }
    }

    private fun gameModeName(mode: Int?): String {
        return when (mode) {
            GameManager.GAME_MODE_UNSUPPORTED -> "UNSUPPORTED"
            GameManager.GAME_MODE_STANDARD -> "STANDARD"
            GameManager.GAME_MODE_PERFORMANCE -> "PERFORMANCE"
            GameManager.GAME_MODE_BATTERY -> "BATTERY"
            null -> "UNAVAILABLE"
            else -> "UNKNOWN_$mode"
        }
    }

    private fun runOnUiThreadBlocking(action: () -> Unit) {
        if (Looper.myLooper() == Looper.getMainLooper()) {
            action()
            return
        }
        val latch = CountDownLatch(1)
        var failure: Throwable? = null
        activity.runOnUiThread {
            try {
                action()
            } catch (error: Throwable) {
                failure = error
            } finally {
                latch.countDown()
            }
        }
        if (!latch.await(2, TimeUnit.SECONDS)) {
            Log.w(TAG, "Timed out waiting for UI-thread game authority update.")
        }
        failure?.let { throw it }
    }

    private companion object {
        const val TAG = "PolymathGameAuthority"
    }
}
