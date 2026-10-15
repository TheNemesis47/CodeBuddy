package dev.codebuddy.pycharm

import com.intellij.openapi.actionSystem.ActionUpdateThread
import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.actionSystem.CommonDataKeys
import com.intellij.openapi.command.WriteCommandAction
import com.intellij.psi.PsiDocumentManager

/**
 * "CodeBuddy: Clear Triggers": removes every `#?` / `#!cmd` line from the current file.
 * The only place the plugin writes to a document (golden rule 2, `scripts/guard-no-edits`).
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
            for (line in lines) {
                val start = document.getLineStartOffset(line)
                val end = if (line + 1 < document.lineCount) document.getLineStartOffset(line + 1) else document.getLineEndOffset(line)
                document.deleteString(start, end)
            }
        }, file)
    }
}
