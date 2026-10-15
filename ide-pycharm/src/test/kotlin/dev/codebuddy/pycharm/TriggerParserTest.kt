package dev.codebuddy.pycharm

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class TriggerParserTest {
    @Test
    fun questionsAndTheoryFire() {
        assertEquals(Trigger(TriggerKind.QUESTION, "perché non chiude il file?"), TriggerParser.parse("#? perché non chiude il file?"))
        assertEquals(Trigger(TriggerKind.QUESTION, "spazi"), TriggerParser.parse("    #?   spazi   "))
        assertEquals(Trigger(TriggerKind.THEORY, "context manager"), TriggerParser.parse("#!teoria context manager"))
        assertEquals(Trigger(TriggerKind.THEORY, "decoratori"), TriggerParser.parse("#!TEORIA decoratori"))
        assertEquals(Trigger(TriggerKind.THEORY, "generators"), TriggerParser.parse("#!theory generators"))
        assertEquals(Trigger(TriggerKind.THEORY, ""), TriggerParser.parse("#!teoria"))
        assertEquals(Trigger(TriggerKind.THEORY, "context manager"), TriggerParser.parse("#! teoria context manager"))
        assertEquals(Trigger(TriggerKind.THEORY, ""), TriggerParser.parse("#!   theory"))
    }

    @Test
    fun normalCommentsDoNotFire() {
        for (line in listOf("# teoria context manager", "# ? no", "#?", "#!", "#!alt", "#!review x", "#!boh x", "#! boh x", "#!/usr/bin/env python3", "x = 1  #? why", "")) {
            assertNull(line, TriggerParser.parse(line))
        }
    }

    @Test
    fun unknownCommandsAreNamedButShebangsAndKnownOnesAreNot() {
        assertEquals("boh", TriggerParser.unknownCommand("#!boh x"))
        assertEquals("alt", TriggerParser.unknownCommand("    #! alt"))
        for (line in listOf("#!teoria x", "#! THEORY", "#!/usr/bin/env python3", "#! /usr/bin/env python3", "#!", "#!  ", "#? q", "# boh", "#!py3 x")) {
            assertNull(line, TriggerParser.unknownCommand(line))
        }
    }
}
