plugins {
    alias(libs.plugins.android.application)
}

android {
    namespace = "app.dartsscorer.spike"
    compileSdk = 36
    defaultConfig {
        applicationId = "app.dartsscorer.spike"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "spike"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_21
        targetCompatibility = JavaVersion.VERSION_21
    }
}

kotlin {
    jvmToolchain(21)
}
