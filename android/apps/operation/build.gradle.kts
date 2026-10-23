plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.bitora.android.operation"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.bitora.operation"
        minSdk = 26
        targetSdk = 35
        versionCode = 103
        versionName = "0.11.1-a11"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    val labBaseUrl = providers.gradleProperty("bitoraPairingBaseUrl").orElse("").get()
    val productionBaseUrl = providers.gradleProperty("bitoraProductionBaseUrl").orElse("").get()
    val releaseStorePath = providers.environmentVariable("BITORA_ANDROID_KEYSTORE_PATH").orNull
    val releaseStorePassword = providers.environmentVariable("BITORA_ANDROID_KEYSTORE_PASSWORD").orNull
    val releaseKeyAlias = providers.environmentVariable("BITORA_ANDROID_KEY_ALIAS").orNull
    val releaseKeyPassword = providers.environmentVariable("BITORA_ANDROID_KEY_PASSWORD").orNull
    signingConfigs {
        if (listOf(releaseStorePath, releaseStorePassword, releaseKeyAlias, releaseKeyPassword).all { !it.isNullOrBlank() }) {
            create("release") {
                storeFile = file(releaseStorePath!!)
                storePassword = releaseStorePassword
                keyAlias = releaseKeyAlias
                keyPassword = releaseKeyPassword
                enableV2Signing = true
                enableV3Signing = true
            }
        }
    }
    buildTypes {
        debug {
            applicationIdSuffix = ".alpha"
            versionNameSuffix = "-debug"
            buildConfigField("String", "BITORA_PAIRING_BASE_URL", "\"$labBaseUrl\"")
            buildConfigField("boolean", "DEV_TOOLS_ENABLED", "true")
            buildConfigField("String", "BITORA_ENVIRONMENT", "\"LAB\"")
            isMinifyEnabled = true
            isShrinkResources = true
            ndk.abiFilters += "arm64-v8a"
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
        release {
            buildConfigField("String", "BITORA_PAIRING_BASE_URL", "\"$productionBaseUrl\"")
            buildConfigField("boolean", "DEV_TOOLS_ENABLED", "false")
            buildConfigField("String", "BITORA_ENVIRONMENT", "\"PRODUCTION\"")
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.findByName("release")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.12.01")
    implementation(project(":shared:foundation"))
    implementation(composeBom)
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.camera:camera-core:1.4.1")
    implementation("androidx.camera:camera-camera2:1.4.1")
    implementation("androidx.camera:camera-lifecycle:1.4.1")
    implementation("androidx.camera:camera-view:1.4.1")
    implementation("com.google.mlkit:barcode-scanning:17.3.0")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
}
