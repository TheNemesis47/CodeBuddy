package dev.codebuddy.pycharm

import com.intellij.codeInsight.editorActions.enter.EnterHandlerDelegate.Result
import com.intellij.codeInsight.editorActions.enter.EnterHandlerDelegateAdapter
import com.intellij.openapi.actionSystem.DataContext
import com.intellij.openapi.components.service
import com.intellij.openapi.editor.Editor
import com.intellij.psi.PsiFile

/**
 * After Enter, looks at the line just finished. On the EDT it does one cheap text check and no
 * PSI, no I/O. A possible trigger goes to [TriggerDispatcher], which does the rest off the EDT.
 */
class TriggerEnterHandler : EnterHandlerDelegateAdapter() {
    override fun postProcessEnter(file: PsiFile, editor: Editor, dataContext: DataContext): Result {
        val document = editor.document
        val line = document.getLineNumber(editor.caretModel.offset) - 1
        if (line < 0) return Result.Continue
        val text = document.charsSequence.subSequence(document.getLineStartOffset(line), document.getLineEndOffset(line))
        if (TriggerParser.parse(text.toString()) != null) {
            file.project.service<TriggerDispatcher>().dispatch(document, line)
        }
        return Result.Continue
    }
}
