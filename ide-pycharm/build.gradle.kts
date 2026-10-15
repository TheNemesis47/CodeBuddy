import org.jetbrains.intellij.platform.gradle.TestFrameworkType

plugins {
    id("org.jetbrains.kotlin.jvm")
    id("org.jetbrains.intellij.platform")
}

kotlin {
    jvmToolchain(21)
}

dependencies {
    testImplementation("junit:junit:4.13.2")

    intellijPlatform {
        // The PyCharm installed on this machine when there is one (no multi-GB download); on CI
        // and on Linux/Windows machines without it, the same version from JetBrains.
        val localPyCharm = providers.gradleProperty("pycharmPath").orNull?.takeIf { file(it).exists() }
        if (localPyCharm != null) {
            local(localPyCharm)
        } else {
            create("PY", providers.gradleProperty("pycharmVersion").getOrElse("2026.2.3"))
        }
        bundledPlugin("PythonCore")
        testFramework(TestFrameworkType.Platform)
    }
}

intellijPlatform {
    pluginConfiguration {
        ideaVersion {
            sinceBuild = "262"
        }
    }
    // Searchable options need a headless IDE run; nothing to index in this plugin.
    buildSearchableOptions = false
}

tasks.test {
    // Tests read the shared protocol examples (the contract with the brain).
    systemProperty("codebuddy.protocolDir", rootProject.projectDir.resolve("../protocol").absolutePath)
    // Live tests (end-to-end, latency bench) need a running brain: only with -Pe2e (never in
    // scripts/check).
    if (!providers.gradleProperty("e2e").isPresent) {
        exclude("**/Live*Test*")
    }
    for (name in listOf("BUDDY_PORT", "BUDDY_HOME")) {
        providers.environmentVariable(name).orNull?.let { environment(name, it) }
    }
}
