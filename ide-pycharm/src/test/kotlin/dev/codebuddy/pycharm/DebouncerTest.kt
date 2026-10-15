package dev.codebuddy.pycharm

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.concurrent.Future
import java.util.concurrent.FutureTask

/** The idle debounce on a manual clock: no sleeping, no threads. */
class DebouncerTest {
    private class ManualClock(private val honourCancel: Boolean = true) {
        var now = 0L
        private val tasks = mutableListOf<Pair<Long, FutureTask<*>>>()

        fun schedule(delay: Long, task: Runnable): Future<*> {
            val future = FutureTask<Unit>({ task.run() }, Unit)
            tasks += (now + delay) to future
            return if (honourCancel) future else object : Future<Unit> by future {
                override fun cancel(mayInterruptIfRunning: Boolean) = false // a cancel that came too late
            }
        }

        fun advance(ms: Long) {
            now += ms
            tasks.filter { it.first <= now }.forEach { (_, task) -> tasks.removeIf { it.second === task }; task.run() }
        }
    }

    private fun debouncer(clock: ManualClock, fired: MutableList<String>) =
        Debouncer<String>(IdleDispatcher.IDLE_DELAY_MS, clock::schedule) { fired += "${it}@${clock.now}" }

    @Test
    fun firesOnceFourSecondsAfterTheLastKeystroke() {
        assertEquals(4_000L, IdleDispatcher.IDLE_DELAY_MS)
        val clock = ManualClock()
        val fired = mutableListOf<String>()
        val debouncer = debouncer(clock, fired)
        debouncer.touch("a.py")
        clock.advance(3_000)
        debouncer.touch("a.py") // still typing: the timer restarts
        clock.advance(3_999)
        assertTrue(fired.isEmpty())
        assertTrue(debouncer.isPending("a.py"))
        clock.advance(1)
        assertEquals(listOf("a.py@7000"), fired)
        assertFalse(debouncer.isPending("a.py"))
        clock.advance(60_000)
        assertEquals(1, fired.size)
    }

    @Test
    fun documentsAreDebouncedSeparately() {
        val clock = ManualClock()
        val fired = mutableListOf<String>()
        val debouncer = debouncer(clock, fired)
        debouncer.touch("a.py")
        clock.advance(2_000)
        debouncer.touch("b.py")
        clock.advance(2_000)
        assertEquals(listOf("a.py@4000"), fired)
        clock.advance(2_000)
        assertEquals(listOf("a.py@4000", "b.py@6000"), fired)
    }

    @Test
    fun aTimerThatCouldNotBeCancelledDoesNotFire() {
        val clock = ManualClock(honourCancel = false)
        val fired = mutableListOf<String>()
        val debouncer = debouncer(clock, fired)
        debouncer.touch("a.py")
        clock.advance(1_000)
        debouncer.touch("a.py")
        clock.advance(3_000) // the first timer runs, but it's stale
        assertTrue(fired.isEmpty())
        clock.advance(1_000)
        assertEquals(listOf("a.py@5000"), fired)
    }

    @Test
    fun cancelAllStopsEverything() {
        val clock = ManualClock()
        val fired = mutableListOf<String>()
        val debouncer = debouncer(clock, fired)
        debouncer.touch("a.py")
        debouncer.cancelAll()
        clock.advance(10_000)
        assertTrue(fired.isEmpty())
    }
}
