package dev.codebuddy.pycharm

import com.google.gson.JsonParser
import com.intellij.openapi.components.service
import com.intellij.testFramework.PlatformTestUtil
import com.intellij.openapi.application.ApplicationManager
import com.intellij.testFramework.replaceService
import com.intellij.testFramework.fixtures.BasePlatformTestCase
import java.io.File
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.TimeUnit

/** Enter → trigger message, the clear action, and message shapes against `protocol/examples`. */
class PluginFlowTest : BasePlatformTestCase() {
    private class RecordingSender : BrainSender {
        val sent = CopyOnWriteArrayList<Pair<ProjectMap, String>>()
        override fun send(map: ProjectMap, message: String) {
            sent += map to message
        }
    }

    private lateinit var sender: RecordingSender

    override fun setUp() {
        super.setUp()
        sender = RecordingSender()
        ApplicationManager.getApplication().replaceService(BrainSender::class.java, sender, testRootDisposable)
    }

    private fun pressEnterAfter(text: String): List<Pair<ProjectMap, String>> {
        myFixture.configureByText("load.py", text)
        myFixture.type('\n')
        project.service<TriggerDispatcher>().lastDispatch?.let { PlatformTestUtil.waitForPromise(it, TimeUnit.SECONDS.toMillis(10)) }
        PlatformTestUtil.dispatchAllEventsInIdeEventQueue()
        return sender.sent
    }

    fun testEnterAfterAQuestionSendsATrigger() {
        val sent = pressEnterAfter("def load(path):\n    #? perché non chiude il file?<caret>\n    return open(path)\n")
        assertEquals(1, sent.size)
        val message = JsonParser.parseString(sent[0].second).asJsonObject
        assertEquals("trigger", message["type"].asString)
        assertEquals("question", message["kind"].asString)
        assertEquals("perché non chiude il file?", message["text"].asString)
        assertEquals(2, message["line"].asInt)
        assertEquals("load.py", message["file"].asString)
        assertEquals(sent[0].first.hash, message["project"].asString)
        assertTrue(message["scope"].asString.startsWith("def load(path):"))
    }

    fun testEnterAfterTheoryWithoutTopicSendsATrigger() {
        val sent = pressEnterAfter("#!teoria<caret>\nx = 1\n")
        assertEquals("theory", JsonParser.parseString(sent.single().second).asJsonObject["kind"].asString)
    }

    fun testEnterAfterNormalLinesSendsNothing() {
        assertEmpty(pressEnterAfter("# teoria context manager<caret>\n"))
        assertEmpty(pressEnterAfter("s = \"\"\"\n#? inside a string<caret>\n\"\"\"\n"))
        assertEmpty(pressEnterAfter("x = 1  #? trailing<caret>\n"))
        assertEmpty(pressEnterAfter("print('hi')<caret>\n"))
    }

    fun testClearTriggersRemovesOnlyTriggerLines() {
        myFixture.configureByText(
            "load.py",
            "def load(path):\n    #? why\n    # teoria keep me\n    s = \"#? keep\"\n    #!teoria with\n    return s\n",
        )
        myFixture.testAction(ClearTriggersAction())
        assertEquals("def load(path):\n    # teoria keep me\n    s = \"#? keep\"\n    return s\n", myFixture.editor.document.text)
    }

    fun testMessagesHaveTheSameKeysAsTheProtocolExamples() {
        val examples = File(System.getProperty("codebuddy.protocolDir"), "examples")
        fun keys(json: String) = JsonParser.parseString(json).asJsonObject.keySet()
        fun exampleKeys(name: String) = keys(File(examples, "$name.json").readText())

        val context = CodeContext("a.py", 1, "python", 1, "x = 1", null)
        val map = ProjectMap(listOf("a.py"), mapOf("a.py" to listOf("def f()")))
        assertEquals(exampleKeys("trigger.question"), keys(Messages.trigger("id", Trigger(TriggerKind.QUESTION, "q"), context, map.hash)))
        assertEquals(exampleKeys("idle"), keys(Messages.idle("id", context, map.hash)))
        assertEquals(exampleKeys("project_map"), keys(Messages.projectMap(map)))
        assertEquals(exampleKeys("hello.ide"), keys(Messages.hello("t".repeat(64))))
        val hello = JsonParser.parseString(Messages.hello("t".repeat(64))).asJsonObject
        assertEquals("ide", hello["role"].asString)
        assertEquals(0, hello["v"].asInt)
    }

    // --- idle (G6) -------------------------------------------------------------------------

    private val idle get() = project.service<IdleDispatcher>()

    /** What the 4 s timer would do, without waiting 4 s. */
    private fun fireIdle(): List<Pair<ProjectMap, String>> {
        val before = sender.sent.size
        idle.fire(myFixture.editor.document)
        idle.lastDispatch?.let { PlatformTestUtil.waitForPromise(it, TimeUnit.SECONDS.toMillis(10)) }
        PlatformTestUtil.dispatchAllEventsInIdeEventQueue()
        return sender.sent.drop(before)
    }

    fun testTypingInAPythonFileSchedulesAnIdleAndSendsNothingYet() {
        myFixture.configureByText("load.py", "def load(path):\n    <caret>\n")
        myFixture.type("data = ")
        assertTrue(idle.isPending(myFixture.editor.document))
        assertEmpty(sender.sent) // nothing is built or sent on the EDT while typing
    }

    fun testTypingInOtherFilesSchedulesNothing() {
        myFixture.configureByText("notes.txt", "<caret>")
        myFixture.type("hello")
        assertFalse(idle.isPending(myFixture.editor.document))
    }

    fun testIdleSendsTheContextAroundTheCursor() {
        myFixture.configureByText("load.py", "import json\n\ndef load(path):\n    with open(path) as f:\n        <caret>\n")
        myFixture.type("data = ")
        val sent = fireIdle()
        assertEquals(1, sent.size)
        val message = JsonParser.parseString(sent[0].second).asJsonObject
        assertEquals("idle", message["type"].asString)
        assertEquals("load.py", message["file"].asString)
        assertEquals(5, message["line"].asInt)
        assertEquals("python", message["language"].asString)
        assertEquals(1, message["window"].asJsonObject["start"].asInt)
        assertTrue(message["window"].asJsonObject["code"].asString.contains("        data = "))
        assertTrue(message["scope"].asString.startsWith("def load(path):"))
        assertEquals(sent[0].first.hash, message["project"].asString)
    }

    fun testIdleIsNotSentAgainForUnchangedCode() {
        myFixture.configureByText("load.py", "def load(path):\n    <caret>\n")
        myFixture.type("x")
        assertEquals(1, fireIdle().size)
        myFixture.type("y")
        myFixture.type('\b') // back to the same code: nothing new to say
        assertEmpty(fireIdle())
        myFixture.type("z")
        assertEquals(1, fireIdle().size)
    }

    fun testBrainDownIsSilentAndQuick() {
        val connection = BrainConnection()
        try {
            val started = System.nanoTime()
            // Nothing listens on 8790 in tests (or the token is missing): send must not throw or block.
            connection.send(ProjectMap(emptyList(), emptyMap()), "{}")
            assertTrue(TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - started) < 200)
        } finally {
            connection.dispose()
        }
    }
}
