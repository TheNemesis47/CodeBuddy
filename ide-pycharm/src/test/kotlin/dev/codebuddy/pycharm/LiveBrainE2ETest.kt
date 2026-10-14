package dev.codebuddy.pycharm

import com.intellij.openapi.application.ReadAction
import com.intellij.openapi.components.service
import com.intellij.testFramework.PlatformTestUtil
import com.intellij.testFramework.fixtures.BasePlatformTestCase

/**
 * The plugin's real code path against a running brain. Excluded from the gate; run by hand:
 *   BUDDY_PORT=… BUDDY_HOME=… ./gradlew test -Pe2e --tests '*LiveBrainE2ETest*'
 * with `buddy serve` (and the notch, to see the answer) already running.
 */
class LiveBrainE2ETest : BasePlatformTestCase() {
    fun testTriggerReachesTheBrain() {
        myFixture.configureByText(
            "load.py",
            "import json\n\n\ndef load(path):\n    #? perché non chiude il file?\n    data = json.load(open(path))\n    return data\n",
        )
        val document = myFixture.editor.document
        val outgoing = ReadAction.compute<Outgoing?, Throwable> { project.service<TriggerDispatcher>().prepare(document, 4) }
        assertNotNull(outgoing)
        val connection = BrainConnection()
        try {
            connection.send(outgoing!!.map, outgoing.message)
            Thread.sleep(3_000) // the send runs on the connection's own thread
        } finally {
            connection.dispose()
        }
    }

    /** Type, then stop: the real 4 s timer fires and `idle` goes out through BrainConnection. */
    fun testIdleReachesTheBrain() {
        myFixture.configureByText("load.py", "import json\n\n\ndef load(path):\n    f = open(path)\n    <caret>\n")
        myFixture.type("data = json.load(f)")
        val idle = project.service<IdleDispatcher>()
        val document = myFixture.editor.document
        assertTrue(idle.isPending(document))
        val typedAt = System.currentTimeMillis()
        while ((idle.isPending(document) || idle.lastDispatch == null) && System.currentTimeMillis() - typedAt < 10_000) {
            Thread.sleep(50)
        }
        println("idle fired ${System.currentTimeMillis() - typedAt} ms after the last keystroke")
        PlatformTestUtil.waitForPromise(idle.lastDispatch!!, 10_000)
        PlatformTestUtil.dispatchAllEventsInIdeEventQueue()
        Thread.sleep(3_000) // the send runs on the connection's own thread
    }
}
