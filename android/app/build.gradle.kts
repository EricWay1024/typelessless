import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// Read dev secrets from the (gitignored) local.properties and inject as BuildConfig.
val localProps = Properties().apply {
    val f = rootProject.file("local.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}
fun secret(key: String): String = localProps.getProperty(key) ?: ""

// Single source of truth: keep the bundled defaults in sync with shared/defaults.json.
val syncDefaults by tasks.registering(Copy::class) {
    from(rootProject.file("../shared/defaults.json"))
    into(layout.projectDirectory.dir("src/main/assets"))
}
tasks.named("preBuild") { dependsOn(syncDefaults) }

android {
    namespace = "je.yw.typelessless"
    compileSdk = 36

    defaultConfig {
        applicationId = "je.yw.typelessless"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"

        buildConfigField("String", "SONIOX_KEY", "\"${secret("SONIOX_API_KEY")}\"")
        buildConfigField("String", "ANTHROPIC_KEY", "\"${secret("ANTHROPIC_API_KEY")}\"")
    }

    buildFeatures {
        buildConfig = true
    }

    buildTypes {
        getByName("release") {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
}
