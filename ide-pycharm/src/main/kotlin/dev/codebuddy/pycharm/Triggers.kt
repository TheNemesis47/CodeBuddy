package dev.codebuddy.pycharm

/** Protocol v0 trigger kinds (`protocol/schemas/trigger.json`). */
enum class TriggerKind(val wire: String) { QUESTION("question"), THEORY("theory") }

data class Trigger(val kind: TriggerKind, val text: String)

/**
 * Parses the text of one comment: `#? question` or `#!teoria topic`.
 * Mirrors `brain/src/buddy/triggers.py`. `# teoria …`, `#!alt` (after the MVP) and an empty `#?`
 * don't fire. Whether the comment is a whole-line comment is decided by [TriggerDetector] via PSI.
 */
object TriggerParser {
    private val commands = mapOf("teoria" to TriggerKind.THEORY, "theory" to TriggerKind.THEORY)

    fun parse(comment: String): Trigger? {
        val s = comment.trim()
        if (s.startsWith("#?")) {
            val text = s.substring(2).trim()
            return if (text.isEmpty()) null else Trigger(TriggerKind.QUESTION, text)
        }
        if (s.startsWith("#!")) {
            val rest = s.substring(2)
            val command = rest.substringBefore(' ')
            val kind = commands[command.lowercase()] ?: return null
            return Trigger(kind, rest.substringAfter(' ', "").trim())
        }
        return null
    }
}
