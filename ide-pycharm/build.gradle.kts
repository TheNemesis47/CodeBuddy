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
        local(providers.gradleProperty("pycharmPath"))
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
    // The live end-to-end test needs a running brain: only with -Pe2e (never in scripts/check).
    if (!providers.gradleProperty("e2e").isPresent) {
        exclude("**/LiveBrainE2ETest*")
    }
    for (name in listOf("BUDDY_PORT", "BUDDY_HOME")) {
        providers.environmentVariable(name).orNull?.let { environment(name, it) }
    }
}
