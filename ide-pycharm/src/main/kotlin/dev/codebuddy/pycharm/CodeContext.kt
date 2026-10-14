package dev.codebuddy.pycharm

import com.intellij.openapi.editor.Document
import com.intellij.openapi.project.Project
import com.intellij.openapi.project.guessProjectDir
import com.intellij.openapi.vfs.VfsUtilCore
import com.intellij.psi.PsiComment
import com.intellij.psi.PsiElement
import com.intellij.psi.PsiFile
import com.intellij.psi.util.PsiTreeUtil
import com.jetbrains.python.psi.PyClass
import com.jetbrains.python.psi.PyFunction

/** What the brain needs about the code around a line (protocol `trigger`/`idle` fields). */
data class CodeContext(
    val file: String, // relative to the project root
    val line: Int, // 1-based
    val language: String,
    val windowStart: Int, // 1-based line of windowCode's first line
    val windowCode: String,
    val scope: String?,
)

/** Finds `#?` / `#!cmd` triggers through PSI: only real, whole-line comments count. */
object TriggerDetector {
    /** [line] is 0-based (Document convention). Must run in a read action. */
    fun detect(file: PsiFile, document: Document, line: Int): Trigger? {
        if (line < 0 || line >= document.lineCount) return null
        val start = document.getLineStartOffset(line)
        val end = document.getLineEndOffset(line)
        val text = document.charsSequence.subSequence(start, end)
        val firstNonBlank = text.indexOfFirst { !it.isWhitespace() }
        if (firstNonBlank < 0) return null
        // The line's first non-blank character must be inside a comment. That excludes trailing
        // comments (`x = 1  #? why` starts with code) and strings or docstrings (string tokens).
        val comment = commentAt(file, start + firstNonBlank) ?: return null
        return TriggerParser.parse(comment.text)
    }

    /** Every trigger comment in the file, as (0-based line, trigger). */
    fun all(file: PsiFile, document: Document): List<Pair<Int, Trigger>> =
        PsiTreeUtil.collectElementsOfType(file, PsiComment::class.java)
            .map { document.getLineNumber(it.textRange.startOffset) }
            .distinct()
            .mapNotNull { line -> detect(file, document, line)?.let { line to it } }

    private fun commentAt(file: PsiFile, offset: Int): PsiComment? {
        val element = file.findElementAt(offset) ?: return null
        return element as? PsiComment ?: PsiTreeUtil.getParentOfType(element, PsiComment::class.java, false)
    }
}

object ContextBuilder {
    const val WINDOW_RADIUS = 60
    const val MAX_SCOPE_LINES = 300

    /** [line] is 0-based. Must run in a read action. */
    fun build(project: Project, file: PsiFile, document: Document, line: Int): CodeContext {
        val last = document.lineCount - 1
        val clamped = line.coerceIn(0, maxOf(last, 0))
        val from = maxOf(0, clamped - WINDOW_RADIUS)
        val to = minOf(last, clamped + WINDOW_RADIUS)
        val window = if (document.lineCount == 0) "" else document.charsSequence
            .subSequence(document.getLineStartOffset(from), document.getLineEndOffset(to)).toString()
        return CodeContext(
            file = relativePath(project, file),
            line = clamped + 1,
            language = file.language.id.lowercase(),
            windowStart = from + 1,
            windowCode = window,
            scope = enclosingScope(file, document, document.getLineStartOffset(clamped).coerceAtMost(document.textLength)),
        )
    }

    /** Text of the innermost function or class around [offset], decorators included. */
    fun enclosingScope(file: PsiFile, document: Document, offset: Int): String? {
        val text = document.charsSequence
        var probe = offset
        while (probe < text.length && text[probe].isWhitespace() && text[probe] != '\n') probe++
        val element: PsiElement = file.findElementAt(probe) ?: return null
        val owner = PsiTreeUtil.getParentOfType(element, PyFunction::class.java, PyClass::class.java) ?: return null
        val range = owner.textRange
        val lines = document.getLineNumber(range.endOffset) - document.getLineNumber(range.startOffset) + 1
        if (lines > MAX_SCOPE_LINES) return null
        // Start at the beginning of the line so the scope keeps its indentation.
        return text.subSequence(document.getLineStartOffset(document.getLineNumber(range.startOffset)), range.endOffset).toString()
    }

    fun relativePath(project: Project, file: PsiFile): String {
        val vFile = file.virtualFile ?: file.originalFile.virtualFile ?: return file.name
        val root = project.guessProjectDir() ?: return vFile.name
        return VfsUtilCore.getRelativePath(vFile, root) ?: vFile.name
    }
}
