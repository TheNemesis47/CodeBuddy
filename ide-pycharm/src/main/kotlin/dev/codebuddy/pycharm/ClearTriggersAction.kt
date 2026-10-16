package dev.codebuddy.pycharm

import com.intellij.openapi.actionSystem.ActionUpdateThread
import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.actionSystem.CommonDataKeys
import com.intellij.openapi.command.WriteCommandAction
import com.intellij.openapi.editor.Document
import com.intellij.openapi.editor.RangeMarker
import com.intellij.openapi.project.Project
import com.intellij.psi.PsiDocumentManager

/**
 * This file is the only place the plugin writes to a document (golden rule 2,
 * `scripts/guard-no-edits`), and it only ever removes trigger lines (`#?` / `#!cmd`, found by
 * PSI): the user's code is never touched.
 *
 * "CodeBuddy: Clear Triggers": removes every trigger line from the current file.
 */
class ClearTriggersAction : AnAction() {
    override fun getActionUpdateThread() = ActionUpdateThread.BGT

    override fun update(e: AnActionEvent) {
        e.presentation.isEnabledAndVisible = e.project != null && e.getData(CommonDataKeys.EDITOR) != null
    }

    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        val document = e.getData(CommonDataKeys.EDITOR)?.document ?: return
        val documents = PsiDocumentManager.getInstance(project)
        documents.commitDocument(document)
        val file = documents.getPsiFile(document) ?: return
        val lines = TriggerDetector.all(file, document).map { it.first }.sortedDescending()
        if (lines.isEmpty()) return
        WriteCommandAction.runWriteCommandAction(project, "CodeBuddy: Clear Triggers", null, {
            for (line in lines) deleteLine(document, line)
        }, file)
    }
}

/**
 * After Enter, the trigger line goes once the brain has the question (the user asked for it:
 * many `#?` lines left behind took a lot of room). EDT only. Nothing happens unless the marked
 * line is still a trigger as PSI sees it: if the user has edited it since, it stays. One undoable
 * command: Ctrl+Z brings the line back.
 */
object TriggerEraser {
    fun erase(project: Project, document: Document, marker: RangeMarker) {
        try {
            if (!marker.isValid || project.isDisposed || !document.isWritable) return
            val documents = PsiDocumentManager.getInstance(project)
            documents.commitDocument(document)
            val file = documents.getPsiFile(document) ?: return
            val line = document.getLineNumber(marker.startOffset)
            if (document.getLineNumber(marker.endOffset) != line) return
            if (TriggerDetector.detect(file, document, line) == null) return
            WriteCommandAction.runWriteCommandAction(project, "CodeBuddy: Remove Trigger", null, { deleteLine(document, line) }, file)
        } finally {
            marker.dispose()
        }
    }
}

/** [line] and the line break after it (a last line keeps the break before it). */
private fun deleteLine(document: Document, line: Int) {
    val start = document.getLineStartOffset(line)
    val end = if (line + 1 < document.lineCount) document.getLineStartOffset(line + 1) else document.getLineEndOffset(line)
    document.deleteString(start, end)
}
