package dev.codebuddy.pycharm

import com.intellij.openapi.actionSystem.ActionManager
import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.actionSystem.AnActionResult
import com.intellij.openapi.actionSystem.CommonDataKeys
import com.intellij.openapi.actionSystem.ex.AnActionListener
import com.intellij.openapi.application.ReadAction
import com.intellij.openapi.components.Service
import com.intellij.openapi.components.service
import com.intellij.openapi.editor.Document
import com.intellij.openapi.fileEditor.FileDocumentManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.roots.ProjectFileIndex
import com.intellij.psi.PsiDocumentManager
import com.intellij.util.concurrency.AppExecutorUtil
import com.jetbrains.python.PythonLanguage
import org.jetbrains.concurrency.CancellablePromise
import java.util.UUID

/**
 * Ctrl+S / Cmd+S in a Python editor asks the brain for a review of the whole file. Only the
 * explicit save action counts, not PyCharm's autosave (frame switch, run), so it fires when the
 * student decides. On the EDT: an action id and an extension check. The brain decides whether a
 * review is due (only for a changed file, at most one every 30 s).
 */
class SaveReviewListener : AnActionListener {
    override fun afterActionPerformed(action: AnAction, event: AnActionEvent, result: AnActionResult) {
        if (ActionManager.getInstance().getId(action) !in SAVE_ACTIONS) return
        val project = event.project ?: return
        val editor = event.getData(CommonDataKeys.EDITOR) ?: return
        if (FileDocumentManager.getInstance().getFile(editor.document)?.extension != "py") return
        project.service<ReviewDispatcher>().dispatch(editor.document, editor.caretModel.offset)
    }

    companion object {
        val SAVE_ACTIONS = setOf("SaveAll", "SaveDocument")
    }
}

/** Builds the `review` message off the EDT, like [TriggerDispatcher], and sends it. */
@Service(Service.Level.PROJECT)
class ReviewDispatcher(private val project: Project) {
    /** The last dispatch, so tests can wait for it. */
    @Volatile
    var lastDispatch: CancellablePromise<Outgoing?>? = null
        private set

    fun dispatch(document: Document, offset: Int) {
        lastDispatch = ReadAction.nonBlocking<Outgoing?> { prepare(document, offset) }
            .withDocumentsCommitted(project)
            .expireWith(project)
            .submit(AppExecutorUtil.getAppExecutorService())
            .onSuccess { outgoing -> if (outgoing != null) service<BrainSender>().send(outgoing.map, outgoing.message) }
    }

    /** Must run in a read action with the document committed. */
    fun prepare(document: Document, offset: Int): Outgoing? {
        val file = PsiDocumentManager.getInstance(project).getPsiFile(document) ?: return null
        val vFile = file.virtualFile ?: return null
        if (!file.language.isKindOf(PythonLanguage.getInstance()) || !ProjectFileIndex.getInstance(project).isInContent(vFile)) return null
        val line = document.getLineNumber(offset.coerceIn(0, document.textLength))
        val around = ContextBuilder.build(project, file, document, line)
        // The whole file, so the review sees every class; a file too big for the protocol falls
        // back to the window around the cursor (the brain trims to its token budget anyway).
        val context = if (document.textLength <= MAX_FILE_CHARS) {
            around.copy(windowStart = 1, windowCode = document.text, scope = null)
        } else {
            around
        }
        val map = ProjectMapBuilder.build(project)
        return Outgoing(map, Messages.review(UUID.randomUUID().toString(), context, map.hash))
    }

    companion object {
        const val MAX_FILE_CHARS = 200_000 // protocol/schemas/review.json, window.code maxLength
    }
}
