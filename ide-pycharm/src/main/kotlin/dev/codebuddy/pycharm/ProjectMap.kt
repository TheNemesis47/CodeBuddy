package dev.codebuddy.pycharm

import com.intellij.openapi.project.Project
import com.intellij.openapi.project.guessProjectDir
import com.intellij.openapi.roots.ProjectFileIndex
import com.intellij.openapi.vfs.VfsUtilCore
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.psi.PsiManager
import com.jetbrains.python.psi.PyFile
import java.security.MessageDigest

/** File tree + top-level Python signatures (protocol `project_map`). */
data class ProjectMap(val tree: List<String>, val symbols: Map<String, List<String>>) {
    val hash: String by lazy {
        val digest = MessageDigest.getInstance("SHA-256").digest(Messages.projectMap(this, hashOverride = "").toByteArray())
        digest.take(8).joinToString("") { "%02x".format(it) }
    }
}

object ProjectMapBuilder {
    const val MAX_FILES = 2000
    private val sourceExtensions = setOf("py", "pyi", "toml", "cfg", "md", "txt", "json", "yaml", "yml", "ini", "sql")

    /** Must run in a read action. Skips excluded and ignored files (venvs, caches, build output). */
    fun build(project: Project): ProjectMap {
        val index = ProjectFileIndex.getInstance(project)
        val root = project.guessProjectDir() ?: return ProjectMap(emptyList(), emptyMap())
        val files = mutableListOf<VirtualFile>()
        VfsUtilCore.iterateChildrenRecursively(
            root,
            { it.isValid && index.isInContent(it) && !index.isExcluded(it) && !it.name.startsWith(".") },
            { file ->
                if (!file.isDirectory && file.extension?.lowercase() in sourceExtensions) files += file
                files.size < MAX_FILES
            },
        )
        val psiManager = PsiManager.getInstance(project)
        val tree = mutableListOf<String>()
        val symbols = sortedMapOf<String, List<String>>()
        for (file in files.sortedBy { it.path }) {
            val path = VfsUtilCore.getRelativePath(file, root) ?: continue
            tree += path
            val py = psiManager.findFile(file) as? PyFile ?: continue
            val signatures = topLevelSignatures(py)
            if (signatures.isNotEmpty()) symbols[path] = signatures
        }
        return ProjectMap(tree, symbols)
    }

    fun topLevelSignatures(file: PyFile): List<String> =
        file.topLevelClasses.map { "class ${it.name}" } +
            file.topLevelFunctions.map { "def ${it.name}${it.parameterList.text}" }
}
