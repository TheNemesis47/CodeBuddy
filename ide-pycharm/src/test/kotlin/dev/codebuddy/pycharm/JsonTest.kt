package dev.codebuddy.pycharm

import org.junit.Assert.assertEquals
import org.junit.Test

class JsonTest {
    @Test
    fun encodesProtocolValues() {
        assertEquals(
            """{"s":"a\"b\\c\nd\té","n":1,"b":true,"z":null,"l":[1,"x"],"m":{"k":[]}}""",
            Json.encode(linkedMapOf("s" to "a\"b\\c\nd\té", "n" to 1, "b" to true, "z" to null, "l" to listOf(1, "x"), "m" to mapOf("k" to emptyList<String>()))),
        )
        assertEquals("\"\\u0001\"", Json.encode("\u0001"))
    }

    @Test
    fun mapTrackerSendsTheMapOnlyWhenItChangesOrAfterAReset() {
        val tracker = MapTracker()
        val a = ProjectMap(listOf("a.py"), emptyMap())
        val b = ProjectMap(listOf("a.py", "b.py"), emptyMap())
        assertEquals(2, tracker.messagesFor(a, "t1").size)
        assertEquals(listOf("t2"), tracker.messagesFor(a, "t2"))
        assertEquals(2, tracker.messagesFor(b, "t3").size)
        tracker.reset()
        assertEquals(2, tracker.messagesFor(b, "t4").size)
    }

    @Test
    fun configReadsPortAndHomeFromTheEnvironment() {
        val config = BrainConfig.fromEnvironment(mapOf("BUDDY_PORT" to "8799", "BUDDY_HOME" to "/tmp/cb"))
        assertEquals("ws://127.0.0.1:8799/ws", config.uri.toString())
        assertEquals("/tmp/cb/token", config.tokenFile.toString())
        assertEquals("ws://127.0.0.1:8790/ws", BrainConfig.fromEnvironment(emptyMap()).uri.toString())
    }
}
