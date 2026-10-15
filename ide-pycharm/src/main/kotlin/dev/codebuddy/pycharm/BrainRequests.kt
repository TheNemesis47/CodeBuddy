package dev.codebuddy.pycharm

import com.google.gson.JsonObject
import com.google.gson.JsonParser
import com.intellij.openapi.application.ApplicationManager
import java.net.http.HttpClient
import java.net.http.WebSocket
import java.time.Duration
import java.util.concurrent.CompletableFuture
import java.util.concurrent.CompletionStage
import java.util.concurrent.TimeUnit

/**
 * Request → reply with the brain, for the settings page: its own short WebSocket (hello, one
 * request, the reply with the same `id`, close), so it never waits behind triggers on the main
 * connection. Blocking with timeouts, and therefore refused on the EDT (golden rule 1).
 */
open class BrainRequests(
    private val config: () -> BrainConfig = { BrainConfig.fromEnvironment() },
    private val replyTimeoutS: Long = REPLY_TIMEOUT_S,
) {
    sealed interface Reply {
        data class Ok(val message: JsonObject) : Reply

        /** [brainDown]: nothing to talk to (no token, refused, timed out), as opposed to the
         *  brain answering `error` (a bad value, with a message for the user). */
        data class Failed(val message: String, val brainDown: Boolean) : Reply
    }

    private val http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(BrainConnection.CONNECT_TIMEOUT_S)).build()

    open fun ask(id: String, message: String): Reply {
        check(ApplicationManager.getApplication()?.isDispatchThread != true) { "BrainRequests.ask must not run on the EDT" }
        val brain = config()
        val token = brain.readToken() ?: return Reply.Failed(NOT_RUNNING, brainDown = true)
        val reply = CompletableFuture<JsonObject>()
        var socket: WebSocket? = null
        return try {
            val ws = http.newWebSocketBuilder()
                .connectTimeout(Duration.ofSeconds(BrainConnection.CONNECT_TIMEOUT_S))
                .buildAsync(brain.uri, Listener(id, reply))
                .get(BrainConnection.CONNECT_TIMEOUT_S + 1, TimeUnit.SECONDS)
            socket = ws
            ws.sendText(Messages.hello(token), true).get(BrainConnection.SEND_TIMEOUT_S, TimeUnit.SECONDS)
            ws.sendText(message, true).get(BrainConnection.SEND_TIMEOUT_S, TimeUnit.SECONDS)
            val answer = reply.get(replyTimeoutS, TimeUnit.SECONDS)
            if (answer["type"]?.asString == "error") {
                Reply.Failed(answer["message"]?.asString ?: "the brain refused the request", brainDown = false)
            } else {
                Reply.Ok(answer)
            }
        } catch (e: Exception) {
            Reply.Failed(NOT_RUNNING, brainDown = true)
        } finally {
            socket?.runCatching { sendClose(WebSocket.NORMAL_CLOSURE, "").orTimeout(1, TimeUnit.SECONDS) }
            socket?.abort()
        }
    }

    /** Collects text frames; completes on the reply with our id (or an error tied to no id). */
    private class Listener(private val id: String, private val reply: CompletableFuture<JsonObject>) : WebSocket.Listener {
        private val buffer = StringBuilder()

        override fun onText(webSocket: WebSocket, data: CharSequence, last: Boolean): CompletionStage<*>? {
            buffer.append(data)
            if (last) {
                val text = buffer.toString()
                buffer.setLength(0)
                runCatching { JsonParser.parseString(text).asJsonObject }.getOrNull()?.let { message ->
                    val replyId = message["id"]
                    val isOurs = replyId != null && !replyId.isJsonNull && replyId.asString == id
                    val isUntiedError = message["type"]?.asString == "error" && (replyId == null || replyId.isJsonNull)
                    if (isOurs || isUntiedError) reply.complete(message)
                }
            }
            webSocket.request(1)
            return null
        }

        override fun onClose(webSocket: WebSocket, statusCode: Int, reason: String): CompletionStage<*>? {
            reply.completeExceptionally(IllegalStateException("closed by the brain ($statusCode)"))
            return null
        }

        override fun onError(webSocket: WebSocket, error: Throwable) {
            reply.completeExceptionally(error)
        }
    }

    companion object {
        /** `models_get` may wait on a remote server for up to 5 s on the brain's side. */
        const val REPLY_TIMEOUT_S = 8L
        const val NOT_RUNNING = "CodeBuddy isn't running. Start it (the panel or `buddy serve`), then reopen this page."
    }
}
