package dev.codebuddy.pycharm

import com.google.gson.JsonObject
import com.google.gson.JsonParser
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.options.ConfigurationException
import com.intellij.testFramework.PlatformTestUtil
import com.intellij.testFramework.fixtures.BasePlatformTestCase
import java.io.File
import java.util.concurrent.CopyOnWriteArrayList

/** The settings page against a scripted brain: what it loads, sends and refuses. */
class SettingsPageTest : BasePlatformTestCase() {
    private val examples = File(System.getProperty("codebuddy.protocolDir"), "examples")

    private fun example(name: String): JsonObject = JsonParser.parseString(File(examples, "$name.json").readText()).asJsonObject

    /** Answers like the brain: `settings` for get/set (echoing what was saved), or [failure]. */
    private inner class ScriptedBrain(var failure: BrainRequests.Reply.Failed? = null) : BrainRequests() {
        val sent = CopyOnWriteArrayList<JsonObject>()
        val onEdt = CopyOnWriteArrayList<Boolean>()

        override fun ask(id: String, message: String): Reply {
            val request = JsonParser.parseString(message).asJsonObject
            sent += request
            onEdt += ApplicationManager.getApplication().isDispatchThread
            failure?.let { return it }
            val reply = example("settings").deepCopy()
            reply.addProperty("id", id)
            if (request["type"].asString == "settings_set") reply.add("settings", request["settings"])
            return Reply.Ok(reply)
        }
    }

    private fun open(brain: ScriptedBrain): CodeBuddyConfigurable {
        val page = CodeBuddyConfigurable(brain)
        page.createComponent()
        val deadline = System.currentTimeMillis() + 10_000
        while (page.status.text == CodeBuddyConfigurable.LOADING && System.currentTimeMillis() < deadline) {
            PlatformTestUtil.dispatchAllEventsInIdeEventQueue()
            Thread.sleep(10)
        }
        return page
    }

    fun testThePageShowsWhatTheBrainSaved() {
        val brain = ScriptedBrain()
        val page = open(brain)
        assertEquals(Provider.OPENAI_COMPATIBLE, page.provider.selectedItem)
        assertEquals("http://10.0.0.2:8080", page.url.text)
        assertTrue(page.allowRemote.isSelected)
        assertTrue(page.autoOffset.isSelected)
        assertTrue(page.status.text.contains("config.toml"))
        assertFalse(page.isModified)
        assertEquals(listOf(false), brain.onEdt)  // loaded off the EDT
        assertEquals("settings_get", brain.sent.single()["type"].asString)
    }

    fun testSwitchingToOpenRouterSendsTheProviderAndOnlyTheTypedKey() {
        val brain = ScriptedBrain()
        val page = open(brain)
        page.provider.selectedItem = Provider.OPENROUTER
        page.model.selectedItem = "z-ai/glm-4.6"
        page.model.editor.item = "z-ai/glm-4.6"
        page.key.text = "sk-or-typed"
        assertTrue(page.isModified)
        page.apply()
        val set = brain.sent.last()
        assertEquals("settings_set", set["type"].asString)
        assertEquals("openrouter", set["settings"].asJsonObject["answers"].asJsonObject["provider"].asString)
        assertEquals("z-ai/glm-4.6", set["settings"].asJsonObject["answers"].asJsonObject["model"].asString)
        assertEquals(setOf("openrouter"), set["keys"].asJsonObject.keySet())
        assertEquals("sk-or-typed", set["keys"].asJsonObject["openrouter"].asString)
        assertEquals("", String(page.key.password))  // never kept in the form after saving
    }

    fun testAFixedOffsetIsSent() {
        val brain = ScriptedBrain()
        val page = open(brain)
        page.autoOffset.isSelected = false
        page.offset.value = 30
        assertTrue(page.isModified)
        page.apply()
        assertEquals(30, brain.sent.last()["settings"].asJsonObject["overlay"].asJsonObject["top_offset"].asInt)
    }

    fun testTheBrainsRefusalIsShownAndNothingChanges() {
        val brain = ScriptedBrain()
        val page = open(brain)
        page.allowRemote.isSelected = false
        brain.failure = BrainRequests.Reply.Failed("http://10.0.0.2:8080 is not this computer: turn on network.allow_remote", brainDown = false)
        val refused = try {
            page.apply()
            null
        } catch (e: ConfigurationException) {
            e
        }
        assertTrue(refused?.message.orEmpty().contains("allow_remote"))
        assertTrue(page.isModified)  // the user's edit is still there to fix
    }

    fun testWithNoBrainThePageSaysSoAndSavesNothing() {
        val brain = ScriptedBrain(BrainRequests.Reply.Failed(BrainRequests.NOT_RUNNING, brainDown = true))
        val page = CodeBuddyConfigurable(brain)
        page.createComponent()
        val deadline = System.currentTimeMillis() + 10_000
        while (page.status.text != BrainRequests.NOT_RUNNING && System.currentTimeMillis() < deadline) {
            PlatformTestUtil.dispatchAllEventsInIdeEventQueue()
            Thread.sleep(10)
        }
        assertEquals(BrainRequests.NOT_RUNNING, page.status.text)
        assertFalse(page.provider.isEnabled)
        assertFalse(page.isModified)
        assertThrows(ConfigurationException::class.java) { page.apply() }
        assertEquals(1, brain.sent.size)
    }

    fun testAnotherProviderStartsFromItsOwnModel() {
        val page = open(ScriptedBrain())
        page.provider.selectedItem = Provider.CLAUDE_CODE
        assertEquals("sonnet", page.form().model)
        page.provider.selectedItem = Provider.OPENROUTER
        assertEquals("", page.form().model)  // not "sonnet" sent to OpenRouter
    }
}
