import java.util.Properties
import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.chaquo.python")
    // JVM screenshot tests of the UI (no device needed): ./gradlew recordRoborazziDebug
    id("io.github.takahirom.roborazzi")
}

android {
    namespace = "com.fxengine.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.fxengine.app"
        minSdk = 26
        targetSdk = 36
        versionCode = 13
        versionName = "2.2.0"
        ndk {
            // Modern phones. Add "x86_64" here to run on an emulator.
            abiFilters += listOf("arm64-v8a")
        }
    }

    // Release signing key: never committed. Read from android/keystore.properties
    // (git-ignored) or from FX_KEYSTORE* environment variables (CI secrets).
    // Without a key, release builds fall back to the debug key (still installable).
    val ksProps = Properties().apply {
        rootProject.file("keystore.properties").takeIf { it.exists() }?.inputStream()?.use { load(it) }
    }
    fun ks(prop: String, env: String): String? = System.getenv(env) ?: ksProps.getProperty(prop)
    val ksPath = ks("storeFile", "FX_KEYSTORE")
    signingConfigs {
        if (ksPath != null) {
            create("fx") {
                storeFile = rootProject.file(ksPath)
                storePassword = ks("storePassword", "FX_KEYSTORE_PASSWORD")
                keyAlias = ks("keyAlias", "FX_KEY_ALIAS")
                keyPassword = ks("keyPassword", "FX_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.findByName("fx") ?: signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
    }

    packaging {
        resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }

    testOptions {
        unitTests {
            isIncludeAndroidResources = true
            all {
                // Robolectric downloads android-all from Maven Central; use Google's mirror.
                it.systemProperty("robolectric.dependency.repo.url",
                    "https://maven-central.storage-download.googleapis.com/maven2")
                it.maxHeapSize = "3g"
            }
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
    }
}

// The Python engine lives at the repository root (../../fxengine) and is the
// single source of truth: it is copied into the build, never duplicated in git.
val syncEngine by tasks.registering(Sync::class) {
    from("../../fxengine") {
        exclude("**/__pycache__/**", "**/*.pyc")
    }
    into(layout.buildDirectory.dir("engine-src/fxengine"))
}

tasks.configureEach {
    if (name != syncEngine.name && name.contains("Python")) {
        dependsOn(syncEngine)
    }
}

chaquopy {
    defaultConfig {
        version = "3.13"
        // Same versions the engine's test-suite is run against (see android/README.md).
        pip {
            install("numpy==1.26.2")
            install("pandas==2.1.3")
            install("python-dateutil==4.0.0")
            install("pytz==2026.6")
            install("tzdata==2026.6")
            install("requests==2.34.2")
            install("urllib3==2.8.0")
            install("idna==3.20")
            install("charset-normalizer==3.5.2")
            install("certifi==2026.10.23")
        }
    }
    sourceSets {
        getByName("main") {
            srcDir("build/engine-src")
        }
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2025.10.01")
    implementation(composeBom)
    implementation("androidx.core:core-ktx:1.17.0")
    implementation("androidx.activity:activity-compose:1.11.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.9.4")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.9.4")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-core")
    debugImplementation("androidx.compose.ui:ui-tooling")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.robolectric:robolectric:4.16.1")
    testImplementation("io.github.takahirom.roborazzi:roborazzi:1.77.0")
    testImplementation("io.github.takahirom.roborazzi:roborazzi-compose:1.77.0")
    testImplementation("androidx.compose.ui:ui-test-junit4")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
