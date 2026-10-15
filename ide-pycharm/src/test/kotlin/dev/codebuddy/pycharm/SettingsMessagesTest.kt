package dev.codebuddy.pycharm

import com.google.gson.JsonObject
import com.google.gson.JsonParser
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files

/** The settings page's messages against `protocol/examples` (the contract with the brain). */
class SettingsMessagesTest {
    private val examples = File(System.getProperty("codebuddy.protocolDir"), "examples")

    private fun example(name: String): JsonObject = JsonParser.parseString(File(examples, "$name.json").readText()).asJsonObject

    private fun parse(json: String): JsonObject = JsonParser.parseString(json).asJsonObject

    @Test
    fun theSettingsReplyIsReadAsTheBrainSendsIt() {
        val view = SettingsView.fromMessage(example("settings"))
        assertEquals(Provider.OPENAI_COMPATIBLE, view.settings.provider)
        assertEquals("http://10.0.0.2:8080", view.settings.url)
        assertEquals(listOf("http://127.0.0.1:8080", "http://10.0.0.2:8080"), view.settings.hintUrls)
        assertTrue(view.settings.allowRemote)
        assertNull(view.settings.topOffset)
        assertEquals(true, view.keysSet["openrouter"])
        assertEquals("/home/me/.config/CodeBuddy/config.toml", view.path)
    }

    @Test
    fun settingsGoBackInTheShapeTheyCameIn() {
        val sent = example("settings")["settings"].asJsonObject
        val settings = BuddySettings.fromWire(sent)
        assertEquals(sent, parse(Json.encode(settings.toWire())))
        assertEquals(settings, BuddySettings.fromWire(parse(Json.encode(settings.toWire()))))
    }

    @Test
    fun messagesHaveTheExamplesKeys() {
        val settings = BuddySettings.fromWire(example("settings")["settings"].asJsonObject)
        assertEquals(example("settings_get").keySet(), parse(SettingsMessages.get("s-1")).keySet())
        val set = parse(SettingsMessages.set("s-2", settings, mapOf("answers_server" to null)))
        assertEquals(example("settings_set").keySet(), set.keySet())
        assertTrue(set["keys"].asJsonObject["answers_server"].isJsonNull)
        assertEquals(example("models_get").keySet(), parse(SettingsMessages.models("m-1", "openai-compatible", "http://10.0.0.2:8080")).keySet())
    }

    @Test
    fun noKeyChangesMeansNoKeysField() {
        assertFalse(parse(SettingsMessages.set("s", BuddySettings(), emptyMap())).has("keys"))
    }

    @Test
    fun aFixedOffsetIsANumberAndAutomaticIsAuto() {
        assertEquals(30, parse(Json.encode(BuddySettings(topOffset = 30).toWire()))["overlay"].asJsonObject["top_offset"].asInt)
        assertEquals("auto", parse(Json.encode(BuddySettings().toWire()))["overlay"].asJsonObject["top_offset"].asString)
    }

    @Test
    fun theServerAddressIsOnlySentForYourOwnServer() {
        val wire = parse(Json.encode(BuddySettings(provider = Provider.OPENROUTER, url = "http://x:1").toWire()))
        assertEquals("", wire["answers"].asJsonObject["url"].asString)
    }

    @Test
    fun engineAddressesAreOnePerLineOrCommaSeparated() {
        assertEquals(
            listOf("http://127.0.0.1:8080", "http://10.0.0.2:8080", "http://a:1"),
            BuddySettings.parseUrls(" http://127.0.0.1:8080\n\nhttp://10.0.0.2:8080 , http://a:1\n"),
        )
    }

    @Test
    fun noBrainMeansAQuickPoliteFailure() {
        val home = Files.createTempDirectory("codebuddy-test")
        val noToken = BrainRequests({ BrainConfig.fromEnvironment(mapOf("BUDDY_HOME" to home.toString(), "BUDDY_PORT" to "1")) })
        val reply = noToken.ask("s-1", SettingsMessages.get("s-1")) as BrainRequests.Reply.Failed
        assertTrue(reply.brainDown)
        Files.writeString(home.resolve("token"), "t".repeat(64))
        val started = System.nanoTime()
        val refused = noToken.ask("s-1", SettingsMessages.get("s-1")) as BrainRequests.Reply.Failed
        assertTrue(refused.brainDown)
        assertEquals(BrainRequests.NOT_RUNNING, refused.message)
        assertTrue("took too long", System.nanoTime() - started < 5_000_000_000L)
    }

    @Test
    fun theFilePathIsShownFromTheHomeFolder() {
        assertEquals("~/.config/CodeBuddy/config.toml", CodeBuddyConfigurable.shortPath("/home/me/.config/CodeBuddy/config.toml", "/home/me"))
        assertEquals("/etc/x.toml", CodeBuddyConfigurable.shortPath("/etc/x.toml", "/home/me"))
    }
}
