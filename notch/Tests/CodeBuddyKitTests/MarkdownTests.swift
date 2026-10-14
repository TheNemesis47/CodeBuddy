import Testing
@testable import CodeBuddyKit

struct MarkdownTests {
    @Test func paragraphsListsAndCode() {
        let blocks = Markdown.parse("""
        Alla riga 6 `open(path)`
        non viene chiuso.

        - uno
          - due
        3. tre

        ```python
        with open(p) as f:
            pass
        ```
        """)
        #expect(blocks == [
            .paragraph(text: "Alla riga 6 `open(path)`\nnon viene chiuso."),
            .listItem(prefix: "•", text: "uno", indent: 0),
            .listItem(prefix: "•", text: "due", indent: 1),
            .listItem(prefix: "3.", text: "tre", indent: 0),
            .codeBlock(lang: "python", code: "with open(p) as f:\n    pass", closed: true),
        ])
    }

    @Test func anUnclosedFenceIsCodeWhileStreaming() {
        #expect(Markdown.parse("Ecco:\n```py\nx = 1") == [
            .paragraph(text: "Ecco:"),
            .codeBlock(lang: "py", code: "x = 1", closed: false),
        ])
    }

    @Test func headingNeedsASpace() {
        #expect(Markdown.parse("## Titolo") == [.heading(level: 2, text: "Titolo")])
        #expect(Markdown.parse("#? not a heading") == [.paragraph(text: "#? not a heading")])
    }

    @Test func quotesAndRules() {
        #expect(Markdown.parse("> nota\n---\n>") == [.quote(text: "nota"), .rule, .quote(text: "")])
    }

    @Test func numberedTextIsNotAlwaysAList() {
        #expect(Markdown.parse("2026.10 è una data") == [.paragraph(text: "2026.10 è una data")])
    }

    @Test func emptyInput() {
        #expect(Markdown.parse("").isEmpty)
    }
}
