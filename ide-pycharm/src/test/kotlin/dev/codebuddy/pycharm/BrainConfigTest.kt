package dev.codebuddy.pycharm

import org.junit.Assert.assertEquals
import org.junit.Test
import java.nio.file.Path

/** The plugin must find the token where the brain writes it (platformdirs), on every OS. */
class BrainConfigTest {
    private val home = Path.of("home").toAbsolutePath().toString()

    private fun tokenFor(os: String, env: Map<String, String> = emptyMap()) =
        BrainConfig.fromEnvironment(env, os, home).tokenFile

    @Test
    fun macUsesApplicationSupport() {
        assertEquals(Path.of(home, "Library", "Application Support", "CodeBuddy", "token"), tokenFor("Mac OS X"))
    }

    @Test
    fun windowsUsesLocalAppData() {
        val local = Path.of("C:", "Users", "me", "AppData", "Local").toString()
        assertEquals(Path.of(local, "CodeBuddy", "token"), tokenFor("Windows 11", mapOf("LOCALAPPDATA" to local)))
        assertEquals(Path.of(home, "AppData", "Local", "CodeBuddy", "token"), tokenFor("Windows 11"))
    }

    @Test
    fun linuxUsesXdgDataHome() {
        assertEquals(Path.of(home, ".local", "share", "CodeBuddy", "token"), tokenFor("Linux"))
        val xdg = Path.of(home, "data").toString()
        assertEquals(Path.of(xdg, "CodeBuddy", "token"), tokenFor("Linux", mapOf("XDG_DATA_HOME" to xdg)))
    }

    @Test
    fun envOverridesWin() {
        val config = BrainConfig.fromEnvironment(mapOf("BUDDY_HOME" to home, "BUDDY_PORT" to "8797"), "Linux", home)
        assertEquals(Path.of(home, "token"), config.tokenFile)
        assertEquals("ws://127.0.0.1:8797/ws", config.uri.toString())
    }
}
