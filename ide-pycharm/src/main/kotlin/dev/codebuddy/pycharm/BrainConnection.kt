package dev.codebuddy.pycharm

import com.intellij.openapi.Disposable
import com.intellij.openapi.diagnostic.logger
import com.intellij.util.concurrency.AppExecutorUtil
import java.net.URI
import java.net.http.HttpClient
import java.net.http.WebSocket
import java.nio.file.Files
import java.nio.file.Path
import java.time.Duration
import java.util.concurrent.CompletionStage
import java.util.concurrent.TimeUnit

/** Where the brain is and how to authenticate (SECURITY.md). Same env vars as the brain. */
data class BrainConfig(val uri: URI, val tokenFile: Path) {
    fun readToken(): String? =
        runCatching { Files.readString(tokenFile).trim() }.getOrNull()?.takeIf { it.length >= 32 }

    companion object {
        fun fromEnvironment(
            env: Map<String, String> = System.getenv(),
            osName: String = System.getProperty("os.name"),
            userHome: String = System.getProperty("user.home"),
        ): BrainConfig {
            val port = env["BUDDY_PORT"]?.toIntOrNull() ?: 8790
            val home = env["BUDDY_HOME"]?.let { Path.of(it) } ?: defaultHome(env, osName, userHome)
            return BrainConfig(URI.create("ws://127.0.0.1:$port/ws"), home.resolve("token"))
        }

        /** The brain's per-user data folder (platformdirs `user_data_dir("CodeBuddy")`). */
        fun defaultHome(env: Map<String, String>, osName: String, userHome: String): Path {
            val os = osName.lowercase()
            return when {
                os.startsWith("mac") -> Path.of(userHome, "Library", "Application Support", "CodeBuddy")
                os.startsWith("windows") ->
                    (env["LOCALAPPDATA"]?.let { Path.of(it) } ?: Path.of(userHome, "AppData", "Local")).resolve("CodeBuddy")
                else ->
                    (env["XDG_DATA_HOME"]?.takeIf { it.isNotBlank() }?.let { Path.of(it) }
                        ?: Path.of(userHome, ".local", "share")).resolve("CodeBuddy")
            }
        }
    }
}

/** Sends messages to the brain. An interface so tests can record instead of connecting. */
interface BrainSender {
    /** Fire-and-forget, never blocks the caller. [map] goes first when the brain hasn't seen it. */
    fun send(map: ProjectMap, message: String)

    /** Like [send]; then [delivered] runs, on a background thread, with whether the brain got it. */
    fun send(map: ProjectMap, message: String, delivered: (Boolean) -> Unit) {
        send(map, message)
        delivered(true)
    }
}

/** Decides when `project_map` must be (re)sent: when it changed, or on a new connection. */
class MapTracker {
    private var sentHash: String? = null

    fun messagesFor(map: ProjectMap, message: String): List<String> {
        if (map.hash == sentHash) return listOf(message)
        sentHash = map.hash
        return listOf(Messages.projectMap(map), message)
    }

    fun reset() {
        sentHash = null
    }
}

/**
 * One WebSocket to the brain, used from a single background thread. Golden rule 1: nothing here
 * runs on the EDT, every step has a timeout, and when the brain is down the plugin stays silent
 * (a debug log, no dialogs) and waits [RETRY_AFTER_MS] before trying again.
 */
class BrainConnection : BrainSender, Disposable {
    private val executor = AppExecutorUtil.createBoundedApplicationPoolExecutor("CodeBuddy brain", 1)
    private val http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(CONNECT_TIMEOUT_S)).build()
    private val tracker = MapTracker()
    private var socket: WebSocket? = null
    private var lastFailureAt = 0L

    override fun send(map: ProjectMap, message: String) {
        executor.execute { deliver(map, message) }
    }

    override fun send(map: ProjectMap, message: String, delivered: (Boolean) -> Unit) {
        executor.execute { delivered(deliver(map, message)) }
    }

    private fun deliver(map: ProjectMap, message: String): Boolean {
        try {
            val ws = open() ?: return false
            for (text in tracker.messagesFor(map, message)) {
                ws.sendText(text, true).get(SEND_TIMEOUT_S, TimeUnit.SECONDS)
            }
            return true
        } catch (e: Exception) {
            log.debug("brain unreachable, dropping message: ${e.message}")
            drop()
            return false
        }
    }

    private fun open(): WebSocket? {
        socket?.let { if (!it.isOutputClosed && !it.isInputClosed) return it }
        drop()
        if (System.currentTimeMillis() - lastFailureAt < RETRY_AFTER_MS) return null
        val config = BrainConfig.fromEnvironment()
        val token = config.readToken()
        if (token == null) {
            lastFailureAt = System.currentTimeMillis()
            log.debug("no brain token at ${config.tokenFile}")
            return null
        }
        return try {
            val ws = http.newWebSocketBuilder()
                .connectTimeout(Duration.ofSeconds(CONNECT_TIMEOUT_S))
                .buildAsync(config.uri, Listener())
                .get(CONNECT_TIMEOUT_S + 1, TimeUnit.SECONDS)
            ws.sendText(Messages.hello(token), true).get(SEND_TIMEOUT_S, TimeUnit.SECONDS)
            tracker.reset()
            socket = ws
            ws
        } catch (e: Exception) {
            lastFailureAt = System.currentTimeMillis()
            log.debug("brain not reachable at ${config.uri}: ${e.message}")
            null
        }
    }

    private fun drop() {
        socket?.abort()
        socket = null
    }

    override fun dispose() {
        executor.execute { drop() }
        executor.shutdown()
    }

    /** The brain answers the IDE only with `welcome` or `error`; we just keep the stream flowing. */
    private class Listener : WebSocket.Listener {
        override fun onText(webSocket: WebSocket, data: CharSequence, last: Boolean): CompletionStage<*>? {
            if (data.contains("\"error\"")) log.debug("brain error: $data")
            webSocket.request(1)
            return null
        }
    }

    companion object {
        private val log = logger<BrainConnection>()
        const val CONNECT_TIMEOUT_S = 2L
        const val SEND_TIMEOUT_S = 3L
        const val RETRY_AFTER_MS = 5_000L
    }
}
