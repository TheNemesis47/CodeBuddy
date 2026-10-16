package dev.codebuddy.pycharm

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.application.ModalityState
import com.intellij.openapi.options.Configurable
import com.intellij.openapi.options.ConfigurationException
import com.intellij.openapi.progress.ProgressManager
import com.intellij.openapi.ui.ComboBox
import com.intellij.ui.components.JBCheckBox
import com.intellij.ui.components.JBLabel
import com.intellij.ui.components.JBPasswordField
import com.intellij.ui.components.JBTextField
import com.intellij.ui.dsl.builder.AlignX
import com.intellij.ui.dsl.builder.Row
import com.intellij.ui.dsl.builder.panel
import java.util.UUID
import javax.swing.DefaultComboBoxModel
import javax.swing.JButton
import javax.swing.JComponent
import javax.swing.JSpinner
import javax.swing.SpinnerNumberModel

/**
 * Settings → Tools → CodeBuddy. The page reads and writes the settings through the brain (which
 * owns the file and checks every value); it never talks to a model or to the network itself.
 * Every brain call runs off the EDT: loading and model lists on a pooled thread, saving under a
 * modal progress (golden rule 1).
 */
class CodeBuddyConfigurable(private val requests: BrainRequests = BrainRequests()) : Configurable {
    private var loaded: SettingsView? = null
    private var disposed = false
    private val pendingClears = mutableSetOf<String>()

    internal val status = JBLabel(LOADING)
    internal val provider = ComboBox(DefaultComboBoxModel(Provider.entries.toTypedArray()))
    internal val model = ComboBox<String>().apply { isEditable = true }
    private val loadModels = JButton("Load models")
    private val modelsStatus = JBLabel()
    internal val url = JBTextField()
    internal val key = JBPasswordField().apply { columns = KEY_COLUMNS }
    private val keyState = JBLabel()
    private val clearKey = JButton("Remove saved key")
    internal val allowRemote = JBCheckBox("Allow servers on other machines, e.g. your Mac over WireGuard (your code goes there)")
    internal val autoOffset = JBCheckBox("Automatic", true)
    internal val offset = JSpinner(SpinnerNumberModel(0, 0, 2000, 1))
    private lateinit var urlRow: Row
    private lateinit var keyRow: Row
    private var component: JComponent? = null
    private var filling = false

    override fun getDisplayName(): String = "CodeBuddy"

    override fun createComponent(): JComponent {
        provider.addActionListener {
            if (!filling) resetModelFor(selectedProvider())
            providerChanged()
        }
        autoOffset.addActionListener { offset.isEnabled = !autoOffset.isSelected }
        loadModels.addActionListener { loadAnswerModels() }
        clearKey.addActionListener {
            selectedProvider().keyName?.let { pendingClears += it }
            key.text = ""
            keyState.text = "will be removed when you press Apply"
        }
        val page = panel {
            row { cell(status).align(AlignX.FILL) }
            group("The model (it answers #?, #!teoria, the hints and the review on save)") {
                row("Provider:") {
                    cell(provider).align(AlignX.FILL)
                        .comment("Claude follows the tutor's rules best; smaller models give away the fix more often.")
                }
                urlRow = row("Server address:") {
                    cell(url).align(AlignX.FILL).comment("e.g. http://127.0.0.1:8080, or http://10.0.0.2:8080 for your Mac over a VPN")
                }
                row("Model:") {
                    cell(model).align(AlignX.FILL).resizableColumn()
                    cell(loadModels)
                }
                row("") { cell(modelsStatus) }
                keyRow = row("API key:") {
                    cell(key).align(AlignX.FILL).resizableColumn()
                    cell(keyState)
                    cell(clearKey)
                }
            }
            group("Network") {
                row { cell(allowRemote) }
            }
            group("Panel on Linux and Windows") {
                row("Space above it:") {
                    cell(autoOffset)
                    cell(offset)
                    label("px").comment("For a top bar the panel opens under. Restart CodeBuddy to apply.")
                }
            }
        }
        component = page
        setEditable(false)
        providerChanged()
        load()
        return page
    }

    private fun selectedProvider(): Provider = provider.selectedItem as? Provider ?: Provider.CLAUDE_CODE

    /** A model name means nothing to another provider: start from that provider's default. */
    private fun resetModelFor(chosen: Provider) {
        val defaults = if (chosen == Provider.CLAUDE_CODE) CLAUDE_MODELS else emptyList()
        model.model = DefaultComboBoxModel(defaults.toTypedArray())
        model.selectedItem = defaults.firstOrNull().orEmpty()
        model.editor.item = defaults.firstOrNull().orEmpty()
        modelsStatus.text = if (chosen == Provider.CLAUDE_CODE) "" else "type a model or press Load models"
    }

    private fun providerChanged() {
        val chosen = selectedProvider()
        if (::urlRow.isInitialized) urlRow.visible(chosen == Provider.OPENAI_COMPATIBLE)
        if (::keyRow.isInitialized) keyRow.visible(chosen.keyName != null)
        if (chosen == Provider.CLAUDE_CODE && model.itemCount == 0) CLAUDE_MODELS.forEach(model::addItem)
        showKeyState()
    }

    private fun showKeyState() {
        val name = selectedProvider().keyName
        keyState.text = when {
            name == null -> ""
            name in pendingClears -> "will be removed when you press Apply"
            loaded?.keysSet?.get(name) == true -> "saved (type a new one to replace it)"
            else -> "not set"
        }
        clearKey.isVisible = name != null && loaded?.keysSet?.get(name) == true
    }

    private fun setEditable(editable: Boolean) {
        listOf(provider, model, loadModels, url, key, clearKey, allowRemote, autoOffset)
            .forEach { it.isEnabled = editable }
        offset.isEnabled = editable && !autoOffset.isSelected
    }

    // The brain, off the EDT

    private fun background(work: () -> Unit) {
        ApplicationManager.getApplication().executeOnPooledThread(work)
    }

    private fun onEdt(work: () -> Unit) {
        ApplicationManager.getApplication().invokeLater({ if (!disposed) work() }, ModalityState.any())
    }

    private fun load() {
        background {
            val id = UUID.randomUUID().toString()
            val reply = requests.ask(id, SettingsMessages.get(id))
            onEdt { show(reply) }
        }
    }

    internal fun show(reply: BrainRequests.Reply) {
        when (reply) {
            is BrainRequests.Reply.Ok -> fill(SettingsView.fromMessage(reply.message))
            is BrainRequests.Reply.Failed -> {
                status.text = reply.message
                setEditable(false)
            }
        }
    }

    internal fun fill(view: SettingsView) {
        filling = true
        try {
            fillFields(view)
        } finally {
            filling = false
        }
    }

    private fun fillFields(view: SettingsView) {
        loaded = view
        pendingClears.clear()
        val s = view.settings
        provider.selectedItem = s.provider
        resetModelFor(s.provider)
        model.selectedItem = s.model
        model.editor.item = s.model
        url.text = s.url
        key.text = ""
        allowRemote.isSelected = s.allowRemote
        autoOffset.isSelected = s.topOffset == null
        offset.value = s.topOffset ?: 0
        val overrides = if (view.overrides.isEmpty()) "" else "<br>Overridden now: ${view.overrides.joinToString("; ")}"
        status.text = "<html>Settings file: ${shortPath(view.path)}$overrides</html>"
        setEditable(true)
        providerChanged()
    }

    private fun loadAnswerModels() {
        val chosen = selectedProvider()
        val typedKey = String(key.password).ifBlank { null }
        modelsStatus.text = "asking…"
        background {
            val id = UUID.randomUUID().toString()
            val reply = requests.ask(id, SettingsMessages.models(id, chosen.wire, url.text.trim(), typedKey))
            onEdt { showModels(reply, model, modelsStatus) }
        }
    }

    private fun showModels(reply: BrainRequests.Reply, combo: ComboBox<String>, label: JBLabel) {
        val message = (reply as? BrainRequests.Reply.Ok)?.message
        val error = when {
            reply is BrainRequests.Reply.Failed -> reply.message
            message?.get("error")?.isJsonNull == false -> message["error"].asString
            else -> null
        }
        if (error != null || message == null) {
            label.text = error ?: "no answer"
            return
        }
        val current = combo.editor.item?.toString().orEmpty()
        val models = message.getAsJsonArray("models").map { it.asString }
        combo.model = DefaultComboBoxModel(models.toTypedArray())
        combo.selectedItem = current.ifBlank { models.firstOrNull().orEmpty() }
        label.text = "${models.size} models"
    }

    // Configurable

    internal fun form(): BuddySettings = BuddySettings(
        provider = selectedProvider(),
        model = (model.editor.item ?: model.selectedItem)?.toString()?.trim().orEmpty(),
        url = url.text.trim(),
        allowRemote = allowRemote.isSelected,
        topOffset = if (autoOffset.isSelected) null else (offset.value as Int),
    )

    internal fun keyChanges(): Map<String, String?> {
        val changes = linkedMapOf<String, String?>()
        pendingClears.forEach { changes[it] = null }
        val typed = String(key.password).trim()
        selectedProvider().keyName?.let { if (typed.isNotEmpty()) changes[it] = typed }
        return changes
    }

    override fun isModified(): Boolean {
        val view = loaded ?: return false
        return form() != view.settings || keyChanges().isNotEmpty()
    }

    override fun apply() {
        if (loaded == null) throw ConfigurationException(BrainRequests.NOT_RUNNING, "CodeBuddy")
        val id = UUID.randomUUID().toString()
        val message = SettingsMessages.set(id, form(), keyChanges())
        val reply = ProgressManager.getInstance().runProcessWithProgressSynchronously<BrainRequests.Reply, Exception>(
            { requests.ask(id, message) },
            "Saving CodeBuddy settings",
            false,
            null,
        )
        when (reply) {
            is BrainRequests.Reply.Ok -> fill(SettingsView.fromMessage(reply.message))
            is BrainRequests.Reply.Failed -> throw ConfigurationException(reply.message, "CodeBuddy")
        }
    }

    override fun reset() {
        loaded?.let(::fill)
    }

    override fun disposeUIResources() {
        disposed = true
        component = null
    }

    companion object {
        /** `~/.config/CodeBuddy/config.toml` rather than the full home folder. */
        fun shortPath(path: String, home: String = System.getProperty("user.home")): String =
            if (home.isNotEmpty() && path.startsWith(home)) "~" + path.removePrefix(home) else path

        const val LOADING = "Loading the settings from CodeBuddy…"
        private const val KEY_COLUMNS = 28
        private val CLAUDE_MODELS = listOf("sonnet", "opus", "haiku")
    }
}
