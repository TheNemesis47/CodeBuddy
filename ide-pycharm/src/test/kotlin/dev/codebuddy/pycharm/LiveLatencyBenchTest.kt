package dev.codebuddy.pycharm

import com.intellij.openapi.application.ReadAction
import com.intellij.openapi.components.service
import com.intellij.testFramework.fixtures.BasePlatformTestCase
import java.nio.file.Files
import java.nio.file.Path

/**
 * G5 latency bench: [SNIPPETS] real `#?` triggers, one at a time, through the plugin's own code
 * (TriggerDispatcher.prepare on PSI, then BrainConnection) to a running brain. Each snippet is a
 * file from this repo with a question inserted above a line. The brain measures first-token
 * latency and appends it to $BUDDY_HOME/latency.jsonl; this test only waits for that line before
 * sending the next trigger, so answers never overlap. Excluded from the gate; run through
 * `scripts/bench-latency`, which starts and stops the brain and the notch.
 */
class LiveLatencyBenchTest : BasePlatformTestCase() {
    /** The question goes above the first line of [path] that contains [anchor]. */
    private data class Snippet(val path: String, val anchor: String, val question: String)

    fun testTenTriggers() {
        val repo = Path.of(System.getProperty("codebuddy.protocolDir")).parent
        val latencyLog = BrainConfig.fromEnvironment().tokenFile.resolveSibling("latency.jsonl")
        val connection = BrainConnection()
        try {
            for ((n, snippet) in SNIPPETS.withIndex()) {
                val source = Files.readString(repo.resolve(snippet.path))
                val lines = source.lines().toMutableList()
                val at = lines.indexOfFirst { snippet.anchor in it }
                assertTrue("`${snippet.anchor}` not found in ${snippet.path}", at >= 0)
                lines.add(at, "${lines[at].takeWhile { it == ' ' }}#? ${snippet.question}")
                myFixture.configureByText(Path.of(snippet.path).fileName.toString(), lines.joinToString("\n"))
                val document = myFixture.editor.document
                val outgoing = ReadAction.compute<Outgoing?, Throwable> {
                    project.service<TriggerDispatcher>().prepare(document, at)
                }
                assertNotNull("no trigger detected in ${snippet.path}:${at + 1}", outgoing)
                val before = countLines(latencyLog)
                connection.send(outgoing!!.map, outgoing.message)
                val sentAt = System.currentTimeMillis()
                while (countLines(latencyLog) == before) {
                    assertTrue("no answer for ${snippet.path} within $ANSWER_TIMEOUT_MS ms",
                        System.currentTimeMillis() - sentAt < ANSWER_TIMEOUT_MS)
                    Thread.sleep(100)
                }
                println("bench ${n + 1}/${SNIPPETS.size} ${snippet.path}:${at + 1} done")
                Thread.sleep(PAUSE_MS) // let the notch settle and save its snapshot
            }
        } finally {
            connection.dispose()
        }
    }

    private fun countLines(path: Path): Int =
        if (Files.exists(path)) Files.readAllLines(path).count { it.isNotBlank() } else 0

    companion object {
        const val ANSWER_TIMEOUT_MS = 120_000L
        const val PAUSE_MS = 1_500L

        /** Varied on purpose: files and permissions, math, time, processes, async, caching, strings, HTTP, AST. */
        private val SNIPPETS = listOf(
            Snippet("brain/src/buddy/auth.py", "os.O_EXCL", "perché O_EXCL e non un semplice open in scrittura?"),
            Snippet("brain/src/buddy/latency.py", "(rank - low)", "come funziona l'interpolazione qui?"),
            Snippet("brain/src/buddy/hints.py", "clock: Callable", "perché time.monotonic e non time.time?"),
            Snippet("brain/src/buddy/claude_cli.py", "stdin.write", "perché il prompt va su stdin e non negli argomenti?"),
            Snippet("brain/src/buddy/answers.py", "async for event", "cosa fa async for su un generatore?"),
            Snippet("brain/src/buddy/prompting.py", "@cache", "a cosa serve @cache su questa funzione?"),
            Snippet("brain/src/buddy/triggers.py", "partition(\" \")", "cosa restituisce partition e perché tre valori?"),
            Snippet("brain/src/buddy/server.py", "add_done_callback", "perché serve un set di task e il done callback?"),
            Snippet("brain/src/buddy/local.py", "trust_env=False) as client:", "cosa succede se il server locale non risponde?"),
            Snippet("brain/src/buddy/context.py", "def enclosing_scope", "come trova la funzione che contiene la riga?"),
        )
    }
}
