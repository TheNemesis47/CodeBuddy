package dev.codebuddy.pycharm

import com.intellij.openapi.Disposable
import com.intellij.openapi.application.ReadAction
import com.intellij.openapi.components.Service
import com.intellij.openapi.components.service
import com.intellij.openapi.editor.Document
import com.intellij.openapi.editor.event.DocumentEvent
import com.intellij.openapi.editor.event.DocumentListener
import com.intellij.openapi.fileEditor.FileDocumentManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.project.ProjectManager
import com.intellij.openapi.roots.ProjectFileIndex
import com.intellij.psi.PsiDocumentManager
import com.intellij.util.concurrency.AppExecutorUtil
import com.intellij.util.containers.ContainerUtil
import com.jetbrains.python.PythonLanguage
import org.jetbrains.concurrency.CancellablePromise
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Future
import java.util.concurrent.TimeUnit

/**
 * Per-key debounce: every [touch] restarts that key's timer, and [action] runs once the key has
 * been quiet for [delayMs]. Keys are independent. Thread-safe; [schedule] decides where the
 * action runs (a pooled thread in the IDE, a manual clock in tests).
 */
class Debouncer<K : Any>(
    private val delayMs: Long,
    private val schedule: (Long, Runnable) -> Future<*>,
    private val action: (K) -> Unit,
) {
    // The token decides who fires: a timer that lost a race with a newer touch finds a
    // different token and does nothing, even if its cancel came too late.
    private val tokens = ConcurrentHashMap<K, Any>()
    private val timers = ConcurrentHashMap<K, Future<*>>()

    fun touch(key: K) {
        val token = Any()
        tokens[key] = token
        timers.put(key, schedule(delayMs) { if (tokens.remove(key, token)) action(key) })?.cancel(false)
    }

    fun isPending(key: K): Boolean = tokens.containsKey(key)

    fun cancelAll() {
        tokens.clear()
        timers.values.forEach { it.cancel(false) }
        timers.clear()
    }
}

/**
 * Sends `idle` when the user stops typing in a Python file for [IDLE_DELAY_MS] (SPEC.md US3).
 * The EDT only records the offset and restarts a timer; PSI, context and the message are built
 * in a non-blocking read action on a pooled thread, like [TriggerDispatcher]. An `idle` for the
 * same file and window as the last one from that document is not sent.
 */
@Service(Service.Level.PROJECT)
class IdleDispatcher(private val project: Project) : Disposable {
    private val offsets = ConcurrentHashMap<Document, Int>()
    private val lastSent: MutableMap<Document, String> = ContainerUtil.createConcurrentWeakMap()
    private val debouncer = Debouncer<Document>(
        IDLE_DELAY_MS,
        { delay, task -> AppExecutorUtil.getAppScheduledExecutorService().schedule(task, delay, TimeUnit.MILLISECONDS) },
        ::fire,
    )

    /** The last idle dispatch, so tests can wait for it. */
    @Volatile
    var lastDispatch: CancellablePromise<Outgoing?>? = null
        private set

    /** EDT: called on every change of a `.py` document. Cheap: a map write and a timer. */
    fun documentChanged(document: Document, offset: Int) {
        offsets[document] = offset
        debouncer.touch(document)
    }

    fun isPending(document: Document): Boolean = debouncer.isPending(document)

    /** The user has been quiet on [document]: build and send the idle message, off the EDT. */
    fun fire(document: Document) {
        val offset = offsets.remove(document) ?: return
        lastDispatch = ReadAction.nonBlocking<Outgoing?> { prepare(document, offset) }
            .withDocumentsCommitted(project)
            .expireWith(this)
            .submit(AppExecutorUtil.getAppExecutorService())
            .onSuccess { outgoing -> if (outgoing != null) service<BrainSender>().send(outgoing.map, outgoing.message) }
    }

    /** Must run in a read action with the document committed. */
    fun prepare(document: Document, offset: Int): Outgoing? {
        val file = PsiDocumentManager.getInstance(project).getPsiFile(document) ?: return null
        val vFile = file.virtualFile ?: return null
        if (!file.language.isKindOf(PythonLanguage.getInstance()) || !ProjectFileIndex.getInstance(project).isInContent(vFile)) return null
        val line = document.getLineNumber(offset.coerceIn(0, document.textLength))
        val context = ContextBuilder.build(project, file, document, line)
        val key = "${context.file}\u0000${context.windowStart}\u0000${context.windowCode}"
        if (lastSent.put(document, key) == key) return null // nothing changed since the last idle
        val map = ProjectMapBuilder.build(project)
        return Outgoing(map, Messages.idle(UUID.randomUUID().toString(), context, map.hash))
    }

    override fun dispose() {
        debouncer.cancelAll()
        offsets.clear()
    }

    companion object {
        const val IDLE_DELAY_MS = 4_000L
    }
}

/**
 * Registered as `editorFactoryDocumentListener`: sees every document change in the IDE. On the EDT
 * it does one string check (a `.py` file) and hands the change to each open project's
 * [IdleDispatcher]; whether the file belongs to that project is checked later, off the EDT.
 */
class IdleDocumentListener : DocumentListener {
    override fun documentChanged(event: DocumentEvent) {
        val document = event.document
        val file = FileDocumentManager.getInstance().getFile(document) ?: return
        if (file.extension != "py") return
        val offset = event.offset + event.newLength
        for (project in ProjectManager.getInstance().openProjects) {
            if (!project.isDisposed) project.service<IdleDispatcher>().documentChanged(document, offset)
        }
    }
}
