package dev.codebuddy.pycharm

/** Protocol v0 trigger kinds (`protocol/schemas/trigger.json`). */
enum class TriggerKind(val wire: String) { QUESTION("question"), THEORY("theory"), DEEPER("deeper") }

data class Trigger(val kind: TriggerKind, val text: String)

/**
 * Parses the text of one comment: `#? question`, `#!teoria topic` or `#!approfondisci [focus]`.
 * Mirrors `brain/src/buddy/triggers.py`. `# teoria …`, `#!alt` (after the MVP) and an empty `#?`
 * don't fire. Whether the comment is a whole-line comment is decided by [TriggerDetector] via PSI.
 */
object TriggerParser {
    private val commands = mapOf(
        "teoria" to TriggerKind.THEORY,
        "theory" to TriggerKind.THEORY,
        "approfondisci" to TriggerKind.DEEPER,
        "approfondimento" to TriggerKind.DEEPER,
        "deeper" to TriggerKind.DEEPER,
    )

    fun parse(comment: String): Trigger? {
        val s = comment.trim()
        if (s.startsWith("#?")) {
            val text = s.substring(2).trim()
            return if (text.isEmpty()) null else Trigger(TriggerKind.QUESTION, text)
        }
        if (s.startsWith("#!")) {
            val rest = s.substring(2).trimStart() // `#! teoria x` works like `#!teoria x`
            val command = rest.substringBefore(' ')
            val kind = commands[command.lowercase()] ?: return null
            return Trigger(kind, rest.substringAfter(' ', "").trim())
        }
        return null
    }

    /**
     * The word after `#!` when it is not a command we know (`#!boh x` → "boh"), so the editor can
     * say so instead of staying silent. Only letters: a shebang (`#!/usr/bin/env`) is not a typo.
     */
    fun unknownCommand(comment: String): String? {
        val s = comment.trim()
        if (!s.startsWith("#!")) return null
        val command = s.substring(2).trimStart().substringBefore(' ')
        if (command.isEmpty() || !command.all(Char::isLetter) || command.lowercase() in commands) return null
        return command
    }
}
