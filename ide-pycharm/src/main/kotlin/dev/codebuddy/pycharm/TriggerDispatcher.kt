package dev.codebuddy.pycharm

import com.intellij.openapi.application.ReadAction
import com.intellij.openapi.components.Service
import com.intellij.openapi.components.service
import com.intellij.openapi.editor.Document
import com.intellij.openapi.project.Project
import com.intellij.psi.PsiDocumentManager
import com.intellij.util.concurrency.AppExecutorUtil
import org.jetbrains.concurrency.CancellablePromise
import java.util.UUID

/** A prepared trigger: what goes to the brain. */
data class Outgoing(val map: ProjectMap, val message: String)

/**
 * Turns "Enter was pressed after line N" into a trigger message, off the EDT: PSI work runs in a
 * non-blocking read action on a pooled thread (committed documents, cancelled on project close),
 * then [BrainSender] sends it on its own thread.
 */
@Service(Service.Level.PROJECT)
class TriggerDispatcher(private val project: Project) {
    /** The last dispatch, so tests can wait for it. */
    @Volatile
    var lastDispatch: CancellablePromise<Outgoing?>? = null
        private set

    fun dispatch(document: Document, line: Int) {
        lastDispatch = ReadAction.nonBlocking<Outgoing?> { prepare(document, line) }
            .withDocumentsCommitted(project)
            .expireWith(project)
            .submit(AppExecutorUtil.getAppExecutorService())
            .onSuccess { outgoing -> if (outgoing != null) service<BrainSender>().send(outgoing.map, outgoing.message) }
    }

    /** Must run in a read action with the document committed. */
    fun prepare(document: Document, line: Int): Outgoing? {
        val file = PsiDocumentManager.getInstance(project).getPsiFile(document) ?: return null
        val trigger = TriggerDetector.detect(file, document, line) ?: return null
        val context = ContextBuilder.build(project, file, document, line)
        val map = ProjectMapBuilder.build(project)
        return Outgoing(map, Messages.trigger(UUID.randomUUID().toString(), trigger, context, map.hash))
    }
}
