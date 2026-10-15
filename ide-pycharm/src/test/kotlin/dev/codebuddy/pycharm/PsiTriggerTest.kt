package dev.codebuddy.pycharm

import com.intellij.testFramework.fixtures.BasePlatformTestCase

/** Trigger detection and context building on real Python PSI. */
class PsiTriggerTest : BasePlatformTestCase() {
    private val source = """
        |import json
        |
        |
        |@cache
        |def load(path):
        |    #? perché non chiude il file?
        |    data = json.load(open(path))
        |    s = "#? in a string"
        |    '''
        |    #? in a docstring-like string
        |    '''
        |    x = 1  #? trailing
        |    # teoria context manager
        |    return data
        |
        |
        |class Store:
        |    def get(self, key):
        |        #!teoria dizionari
        |        return self.items[key]
        |""".trimMargin()

    private fun detectAt(line: Int): Trigger? {
        val file = myFixture.configureByText("load.py", source)
        return TriggerDetector.detect(file, myFixture.editor.document, line)
    }

    fun testWholeLineCommentsFire() {
        assertEquals(Trigger(TriggerKind.QUESTION, "perché non chiude il file?"), detectAt(5))
        assertEquals(Trigger(TriggerKind.THEORY, "dizionari"), detectAt(18))
    }

    fun testStringsDocstringsTrailingAndNormalCommentsDoNot() {
        assertNull(detectAt(7)) // "#? in a string"
        assertNull(detectAt(9)) // inside a triple-quoted string
        assertNull(detectAt(11)) // trailing comment
        assertNull(detectAt(12)) // `# teoria`
        assertNull(detectAt(0)) // code
        assertNull(detectAt(1)) // blank
        assertNull(detectAt(99)) // past the end
    }

    fun testAllFindsOnlyRealTriggers() {
        val file = myFixture.configureByText("load.py", source)
        assertEquals(listOf(5, 18), TriggerDetector.all(file, myFixture.editor.document).map { it.first })
    }

    fun testContextHasWindowScopeAndRelativePath() {
        val file = myFixture.configureByText("load.py", source)
        val context = ContextBuilder.build(project, file, myFixture.editor.document, 5)
        assertEquals("load.py", context.file)
        assertEquals(6, context.line)
        assertEquals("python", context.language)
        assertEquals(1, context.windowStart)
        assertTrue(context.windowCode, context.windowCode.startsWith("import json"))
        assertTrue(context.windowCode, context.windowCode.trimEnd().endsWith("return self.items[key]"))
        assertTrue(context.scope, context.scope!!.startsWith("@cache\ndef load(path):"))
        assertTrue(context.scope, context.scope!!.endsWith("return data"))
    }

    fun testScopeIsTheInnermostMethod() {
        val file = myFixture.configureByText("load.py", source)
        val scope = ContextBuilder.build(project, file, myFixture.editor.document, 18).scope
        assertEquals("    def get(self, key):\n        #!teoria dizionari\n        return self.items[key]", scope)
    }

    fun testTopLevelLineHasNoScopeAndTheWindowIsClamped() {
        val lines = (1..200).joinToString("\n") { "x$it = $it" }
        val file = myFixture.configureByText("big.py", lines)
        val context = ContextBuilder.build(project, file, myFixture.editor.document, 100)
        assertNull(context.scope)
        assertEquals(101 - ContextBuilder.WINDOW_RADIUS, context.windowStart)
        assertEquals(2 * ContextBuilder.WINDOW_RADIUS + 1, context.windowCode.lines().size)
    }

    fun testProjectMapListsFilesAndTopLevelSymbolsAndHashFollowsContent() {
        myFixture.addFileToProject("pkg/models.py", "class User:\n    pass\n\ndef make(name, age=1):\n    pass\n")
        myFixture.addFileToProject("notes.md", "# notes")
        val first = ProjectMapBuilder.build(project)
        assertTrue(first.tree.toString(), first.tree.containsAll(listOf("pkg/models.py", "notes.md")))
        assertEquals(listOf("class User", "def make(name, age=1)"), first.symbols["pkg/models.py"])
        assertEquals(first.hash, ProjectMapBuilder.build(project).hash)
        myFixture.addFileToProject("pkg/extra.py", "def extra():\n    pass\n")
        assertFalse(first.hash == ProjectMapBuilder.build(project).hash)
    }
}
