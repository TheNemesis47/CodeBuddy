package dev.codebuddy.pycharm

/** ide → brain messages of protocol v0. Shapes are checked against `protocol/examples` in tests. */
object Messages {
    const val VERSION = 0
    const val CLIENT = "codebuddy-pycharm/0.1.2"

    fun hello(token: String): String =
        Json.encode(mapOf("v" to VERSION, "type" to "hello", "role" to "ide", "token" to token, "client" to CLIENT))

    fun trigger(id: String, trigger: Trigger, context: CodeContext, projectHash: String?): String =
        Json.encode(
            linkedMapOf(
                "v" to VERSION,
                "type" to "trigger",
                "id" to id,
                "kind" to trigger.kind.wire,
                "text" to trigger.text,
                "file" to context.file,
                "line" to context.line,
                "language" to context.language,
                "window" to mapOf("start" to context.windowStart, "code" to context.windowCode),
                "scope" to context.scope,
                "project" to projectHash,
            ),
        )

    fun idle(id: String, context: CodeContext, projectHash: String?): String = event("idle", id, context, projectHash)

    /** After Ctrl+S: [context]'s window is the whole file. */
    fun review(id: String, context: CodeContext, projectHash: String?): String = event("review", id, context, projectHash)

    private fun event(type: String, id: String, context: CodeContext, projectHash: String?): String =
        Json.encode(
            linkedMapOf(
                "v" to VERSION,
                "type" to type,
                "id" to id,
                "file" to context.file,
                "line" to context.line,
                "language" to context.language,
                "window" to mapOf("start" to context.windowStart, "code" to context.windowCode),
                "scope" to context.scope,
                "project" to projectHash,
            ),
        )

    fun projectMap(map: ProjectMap, hashOverride: String? = null): String =
        Json.encode(
            linkedMapOf(
                "v" to VERSION,
                "type" to "project_map",
                "hash" to (hashOverride ?: map.hash),
                "tree" to map.tree,
                "symbols" to map.symbols,
            ),
        )
}
