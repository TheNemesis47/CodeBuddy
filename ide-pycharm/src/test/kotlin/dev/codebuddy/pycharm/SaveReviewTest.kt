package dev.codebuddy.pycharm

import com.google.gson.JsonParser
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.components.service
import com.intellij.testFramework.PlatformTestUtil
import com.intellij.testFramework.fixtures.BasePlatformTestCase
import com.intellij.testFramework.replaceService
import java.io.File
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.TimeUnit

/** Ctrl+S (the `SaveAll` action) → a `review` of the whole file; nothing for other files or actions. */
class SaveReviewTest : BasePlatformTestCase() {
    private class RecordingSender : BrainSender {
        val sent = CopyOnWriteArrayList<String>()
        override fun send(map: ProjectMap, message: String) {
            sent += message
        }
    }

    private lateinit var sender: RecordingSender

    override fun setUp() {
        super.setUp()
        sender = RecordingSender()
        ApplicationManager.getApplication().replaceService(BrainSender::class.java, sender, testRootDisposable)
    }

    private fun press(actionId: String): List<String> {
        val reviews = project.service<ReviewDispatcher>()
        val before = reviews.lastDispatch
        myFixture.performEditorAction(actionId)
        reviews.lastDispatch?.takeIf { it !== before }?.let { PlatformTestUtil.waitForPromise(it, TimeUnit.SECONDS.toMillis(10)) }
        PlatformTestUtil.dispatchAllEventsInIdeEventQueue()
        return sender.sent
    }

    fun testCtrlSSendsTheWholeFileWithTheCaretLine() {
        val code = "class Rect:\n    def __init__(self, w, h):\n        self.w = w\n\n    def area(self):\n        self.w<caret> * self.h\n"
        myFixture.configureByText("shapes.py", code)
        val message = JsonParser.parseString(press("SaveAll").single()).asJsonObject
        assertEquals("review", message["type"].asString)
        assertEquals("shapes.py", message["file"].asString)
        assertEquals(6, message["line"].asInt)
        assertEquals(1, message["window"].asJsonObject["start"].asInt)
        assertEquals(code.replace("<caret>", ""), message["window"].asJsonObject["code"].asString)
        assertTrue(message["scope"].isJsonNull)
    }

    fun testSavingAnotherKindOfFileSendsNothing() {
        myFixture.configureByText("notes.txt", "hello<caret>")
        assertEmpty(press("SaveAll"))
    }

    fun testOtherActionsSendNothing() {
        myFixture.configureByText("shapes.py", "x = 1<caret>\n")
        assertEmpty(press("EditorLineEnd"))
    }

    fun testAHugeFileSendsOnlyTheCodeAroundTheCursor() {
        val lines = (1..30_000).joinToString("\n") { "x$it = $it" }
        myFixture.configureByText("big.py", lines.replace("x15000 =", "x15000<caret> ="))
        val window = JsonParser.parseString(press("SaveAll").single()).asJsonObject["window"].asJsonObject
        assertTrue(window["code"].asString.length <= ReviewDispatcher.MAX_FILE_CHARS)
        assertTrue(window["code"].asString.contains("x15000 = 15000"))
        assertEquals(15000 - ContextBuilder.WINDOW_RADIUS, window["start"].asInt)
    }

    fun testTheReviewHasTheProtocolExamplesKeys() {
        val example = File(File(System.getProperty("codebuddy.protocolDir"), "examples"), "review.json").readText()
        val context = CodeContext("a.py", 1, "python", 1, "x = 1", null)
        assertEquals(
            JsonParser.parseString(example).asJsonObject.keySet(),
            JsonParser.parseString(Messages.review("id", context, "h")).asJsonObject.keySet(),
        )
    }
}
