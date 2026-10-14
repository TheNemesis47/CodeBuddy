package dev.codebuddy.pycharm

import com.intellij.openapi.application.ReadAction
import com.intellij.openapi.components.service
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
}
