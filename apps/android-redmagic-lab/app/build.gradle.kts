import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
}

val phase1ExecJniLibsDir = layout.buildDirectory.dir("generated/phase1ExecJniLibs")
val phase1ExecJniLibsDirectory = layout.buildDirectory.file("generated/phase1ExecJniLibs").get().asFile
val phase1ExecSource = providers.environmentVariable("POLYMATH_PHASE1_EXECUTABLE")
    .orElse("/tmp/polymath_android_lab_phase1_exact_closure_material_export/android_lab_phase1_exact_closure_material_export/bin/phase1_qa_stream")

android {
    namespace = "ai.zer0pa.polymath.lab"
    compileSdk = 37
    ndkVersion = "28.2.13676358"

    defaultConfig {
        applicationId = "ai.zer0pa.polymath.lab"
        minSdk = 31
        targetSdk = 37
        versionCode = 1
        versionName = "0.1.0-phase1-probe"

        ndk {
            abiFilters += "arm64-v8a"
        }

        externalNativeBuild {
            cmake {
                arguments += listOf("-DANDROID_STL=c++_shared")
                targets += listOf("polymath_lab_native")
            }
        }
    }

    buildTypes {
        debug {
            isDebuggable = true
        }
        create("benchmark") {
            initWith(getByName("release"))
            isDebuggable = false
            signingConfig = signingConfigs.getByName("debug")
            matchingFallbacks += listOf("release")
        }
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
    }

    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
            version = "3.22.1"
        }
    }

    sourceSets {
        getByName("main") {
            jniLibs.srcDir(phase1ExecJniLibsDirectory)
        }
    }

    packaging {
        jniLibs {
            useLegacyPackaging = true
            keepDebugSymbols += setOf("**/libphase1_qa_stream_exec.so")
        }
        resources {
            excludes += setOf(
                "META-INF/AL2.0",
                "META-INF/LGPL2.1",
                "META-INF/LICENSE*",
                "META-INF/NOTICE*"
            )
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
    }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2026.06.00"))
    implementation("androidx.activity:activity-compose:1.13.0")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.runtime:runtime")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")

    debugImplementation("androidx.compose.ui:ui-tooling")
}

val preparePhase1ExecJniLibs by tasks.registering(Copy::class) {
    val sourcePath = phase1ExecSource
    from(sourcePath)
    into(phase1ExecJniLibsDir.map { it.dir("arm64-v8a") })
    rename { "libphase1_qa_stream_exec.so" }
    duplicatesStrategy = DuplicatesStrategy.FAIL
    doFirst {
        val sourceFile = file(sourcePath.get())
        require(sourceFile.isFile) {
            "Phase 1 executable not found at ${sourceFile.absolutePath}; set POLYMATH_PHASE1_EXECUTABLE to the delivered PIE."
        }
    }
}

tasks.matching { it.name.endsWith("JniLibFolders") || it.name.endsWith("NativeLibs") }.configureEach {
    dependsOn(preparePhase1ExecJniLibs)
}
