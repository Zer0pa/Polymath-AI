package ai.zer0pa.polymath.lab.data

import android.content.Context
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.os.Build
import org.json.JSONObject
import java.io.File

class ApkIdentityReader(private val context: Context) {
    fun readIdentity(): JSONObject {
        val packageManager = context.packageManager
        val packageName = context.packageName
        val packageInfo = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            packageManager.getPackageInfo(packageName, PackageManager.PackageInfoFlags.of(0))
        } else {
            @Suppress("DEPRECATION")
            packageManager.getPackageInfo(packageName, 0)
        }
        val applicationInfo = requireNotNull(packageInfo.applicationInfo) {
            "PackageInfo.applicationInfo unavailable for $packageName"
        }
        val sourceFile = File(applicationInfo.sourceDir)
        val nativeLibraryDir = applicationInfo.nativeLibraryDir ?: ""
        val phase1Exec = File(nativeLibraryDir, "libphase1_qa_stream_exec.so")

        return JSONObject()
            .put("schema_version", "apk_identity_v1")
            .put("package_name", packageName)
            .put("version_name", packageInfo.versionName ?: "unknown")
            .put("version_code", packageInfo.longVersionCode)
            .put("application_category", applicationInfo.category)
            .put("application_category_name", categoryName(applicationInfo.category))
            .put("declared_game_category_expected", true)
            .put("source_dir", applicationInfo.sourceDir)
            .put("apk_sha256", sourceFile.takeIf { it.isFile }?.sha256Hex() ?: "unavailable")
            .put("native_library_dir", nativeLibraryDir.ifBlank { "unavailable" })
            .put("phase1_exec_path", phase1Exec.absolutePath)
            .put("phase1_exec_sha256", phase1Exec.takeIf { it.isFile }?.sha256Hex() ?: "unavailable")
    }

    private fun categoryName(category: Int): String {
        return when (category) {
            ApplicationInfo.CATEGORY_GAME -> "game"
            ApplicationInfo.CATEGORY_AUDIO -> "audio"
            ApplicationInfo.CATEGORY_IMAGE -> "image"
            ApplicationInfo.CATEGORY_MAPS -> "maps"
            ApplicationInfo.CATEGORY_NEWS -> "news"
            ApplicationInfo.CATEGORY_PRODUCTIVITY -> "productivity"
            ApplicationInfo.CATEGORY_SOCIAL -> "social"
            ApplicationInfo.CATEGORY_VIDEO -> "video"
            else -> "unknown"
        }
    }
}
