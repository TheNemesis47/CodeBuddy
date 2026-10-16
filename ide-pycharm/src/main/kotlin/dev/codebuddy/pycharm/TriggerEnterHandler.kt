package dev.codebuddy.pycharm

import com.intellij.codeInsight.editorActions.enter.EnterHandlerDelegate.Result
import com.intellij.codeInsight.editorActions.enter.EnterHandlerDelegateAdapter
import com.intellij.codeInsight.hint.HintManager
import com.intellij.openapi.actionSystem.DataContext
import com.intellij.openapi.components.service
import com.intellij.openapi.editor.Editor
import com.intellij.psi.PsiFile

/**
 * After Enter, looks at the line just finished. On the EDT it does one cheap text check and no
 * PSI, no I/O. A possible trigger goes to [TriggerDispatcher], which does the rest off the EDT,
 * with a marker on the line so it can be erased once the brain has it.
 * A `#!word` we don't know gets a small hint at the caret instead of silence.
 */
class TriggerEnterHandler : EnterHandlerDelegateAdapter() {
    override fun postProcessEnter(file: PsiFile, editor: Editor, dataContext: DataContext): Result {
        val document = editor.document
        val line = document.getLineNumber(editor.caretModel.offset) - 1
        if (line < 0) return Result.Continue
        val text = document.charsSequence.subSequence(document.getLineStartOffset(line), document.getLineEndOffset(line))
        if (TriggerParser.parse(text.toString()) != null) {
            val marker = document.createRangeMarker(document.getLineStartOffset(line), document.getLineEndOffset(line))
            file.project.service<TriggerDispatcher>().dispatch(document, line, marker)
        } else {
            TriggerParser.unknownCommand(text.toString())?.let {
                service<EditorHints>().show(editor, unknownCommandHint(it))
            }
        }
        return Result.Continue
    }
}

fun unknownCommandHint(command: String): String =
    "CodeBuddy: il comando #!$command non esiste. Usa #? <domanda>, #!teoria <argomento> o #!approfondisci."

/** A small hint at the caret; an application service so tests can see what was said. */
interface EditorHints {
    fun show(editor: Editor, text: String)
}

class IdeEditorHints : EditorHints {
    override fun show(editor: Editor, text: String) = HintManager.getInstance().showInformationHint(editor, text)
}
