package dev.codebuddy.pycharm

import com.google.gson.JsonElement
import com.google.gson.JsonObject

/**
 * The brain's settings, as the settings page edits them. The brain owns the file and checks
 * every value (brain/src/buddy/settings.py); this side only mirrors the `settings` message.
 */
data class BuddySettings(
    val provider: Provider = Provider.CLAUDE_CODE,
    val model: String = "sonnet",
    val url: String = "",
    val hintUrls: List<String> = listOf("http://127.0.0.1:8080", "http://127.0.0.1:8000"),
    val hintModel: String = "",
    val proactiveCloud: Boolean = false,
    val allowRemote: Boolean = false,
    /** Pixels above the Linux/Windows panel; null = automatic. */
    val topOffset: Int? = null,
) {
    fun toWire(): Map<String, Any?> = linkedMapOf(
        "answers" to linkedMapOf("provider" to provider.wire, "model" to model, "url" to if (provider == Provider.OPENAI_COMPATIBLE) url else ""),
        "hints" to linkedMapOf("urls" to hintUrls, "model" to hintModel, "proactive_cloud" to proactiveCloud),
        "network" to linkedMapOf("allow_remote" to allowRemote),
        "overlay" to linkedMapOf("top_offset" to (topOffset ?: "auto")),
    )

    companion object {
        fun fromWire(json: JsonObject): BuddySettings {
            val answers = json.getAsJsonObject("answers")
            val hints = json.getAsJsonObject("hints")
            val top = json.getAsJsonObject("overlay")["top_offset"]
            return BuddySettings(
                provider = Provider.fromWire(answers["provider"].asString),
                model = answers["model"].asString,
                url = answers["url"].asString,
                hintUrls = hints.getAsJsonArray("urls").map(JsonElement::getAsString),
                hintModel = hints["model"].asString,
                proactiveCloud = hints["proactive_cloud"].asBoolean,
                allowRemote = json.getAsJsonObject("network")["allow_remote"].asBoolean,
                topOffset = if (top.isJsonPrimitive && top.asJsonPrimitive.isNumber) top.asInt else null,
            )
        }

        /** One address per line (or comma-separated); blanks dropped. */
        fun parseUrls(text: String): List<String> =
            text.split('\n', ',').map(String::trim).filter(String::isNotEmpty)
    }
}

enum class Provider(val wire: String, val label: String, val keyName: String?) {
    CLAUDE_CODE("claude-code", "Claude Code (your subscription)", null),
    OPENROUTER("openrouter", "OpenRouter", "openrouter"),
    OPENAI_COMPATIBLE("openai-compatible", "OpenAI-compatible server (llama.cpp, LM Studio, your Mac…)", "answers_server");

    override fun toString(): String = label

    companion object {
        fun fromWire(wire: String): Provider = entries.firstOrNull { it.wire == wire } ?: CLAUDE_CODE
    }
}

/** The `settings` message: the saved settings, which keys are set (never the keys), the file. */
data class SettingsView(
    val settings: BuddySettings,
    val keysSet: Map<String, Boolean>,
    val path: String,
    val overrides: List<String>,
) {
    companion object {
        fun fromMessage(json: JsonObject): SettingsView = SettingsView(
            BuddySettings.fromWire(json.getAsJsonObject("settings")),
            json.getAsJsonObject("keys").entrySet().associate { it.key to it.value.asBoolean },
            json["path"].asString,
            json.getAsJsonArray("overrides").map(JsonElement::getAsString),
        )
    }
}

/** ide → brain messages of the settings page (protocol v0, `settings_*` and `models_get`). */
object SettingsMessages {
    fun get(id: String): String = Json.encode(linkedMapOf("v" to Messages.VERSION, "type" to "settings_get", "id" to id))

    /** [keys]: only the keys to change; a value sets the key, null clears it. */
    fun set(id: String, settings: BuddySettings, keys: Map<String, String?>): String =
        Json.encode(
            linkedMapOf<String, Any?>("v" to Messages.VERSION, "type" to "settings_set", "id" to id, "settings" to settings.toWire())
                .also { if (keys.isNotEmpty()) it["keys"] = keys },
        )

    /** [provider] is a [Provider.wire] or "hints"; [key] tries a key that isn't saved yet. */
    fun models(id: String, provider: String, url: String = "", key: String? = null): String =
        Json.encode(linkedMapOf("v" to Messages.VERSION, "type" to "models_get", "id" to id, "provider" to provider, "url" to url, "key" to key))
}
