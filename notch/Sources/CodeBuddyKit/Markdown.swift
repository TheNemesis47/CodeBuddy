import Foundation

/// Block-level markdown, enough for tutor answers. Inline syntax (`code`, **bold**) is left to
/// `AttributedString(markdown:)` in the view.
/// Adapted from Coucou's chat markdown parser (MIT, © 2026 Louis Raillé, see THIRD_PARTY.md).
public enum MarkdownBlock: Equatable, Sendable {
    case heading(level: Int, text: String)
    case paragraph(text: String)
    /// `closed` is false while the answer is still streaming inside the fence.
    case codeBlock(lang: String, code: String, closed: Bool)
    /// prefix: "•" for unordered, "1." for ordered; indent: nesting level (0-based).
    case listItem(prefix: String, text: String, indent: Int)
    case quote(text: String)
    case rule
}

public enum Markdown {
    /// One plain line for a tight space: markup dropped, whitespace collapsed, cut on a word
    /// boundary with "…". Nil when there is no text yet.
    public static func preview(_ markdown: String, maxCharacters: Int) -> String? {
        let plain = markdown
            .replacingOccurrences(of: "```", with: " ")
            .replacingOccurrences(of: "**", with: "")
            .replacingOccurrences(of: "`", with: "")
            .split(whereSeparator: \.isWhitespace)
            .filter { !["-", "*", "•", ">", "#", "##", "###"].contains($0) }
            .joined(separator: " ")
        guard !plain.isEmpty else { return nil }
        guard plain.count > maxCharacters else { return plain }
        let cut = plain.prefix(maxCharacters)
        let word = cut.lastIndex(of: " ").map { cut[..<$0] } ?? cut
        return word.trimmingCharacters(in: .punctuationCharacters.union(.whitespaces)) + "…"
    }

    public static func parse(_ input: String) -> [MarkdownBlock] {
        var blocks: [MarkdownBlock] = []
        let lines = input.components(separatedBy: "\n")
        var i = 0
        while i < lines.count {
            let line = lines[i]
            let stripped = line.trimmingCharacters(in: .whitespaces)

            if stripped.hasPrefix("```") {
                let lang = String(stripped.dropFirst(3)).trimmingCharacters(in: .whitespaces)
                var code: [String] = []
                i += 1
                while i < lines.count, !lines[i].trimmingCharacters(in: .whitespaces).hasPrefix("```") {
                    code.append(lines[i])
                    i += 1
                }
                let closed = i < lines.count
                blocks.append(.codeBlock(lang: lang, code: code.joined(separator: "\n"), closed: closed))
                i += 1
                continue
            }

            if line.hasPrefix("#") {
                var level = 0
                var rest = Substring(line)
                while rest.hasPrefix("#") { level += 1; rest = rest.dropFirst() }
                if rest.hasPrefix(" ") || rest.isEmpty {
                    let text = rest.trimmingCharacters(in: .whitespaces)
                    if !text.isEmpty { blocks.append(.heading(level: min(level, 6), text: text)) }
                    i += 1
                    continue
                }
            }

            if isRule(stripped) {
                blocks.append(.rule)
                i += 1
                continue
            }

            if stripped.hasPrefix("> ") || stripped == ">" {
                blocks.append(.quote(text: stripped == ">" ? "" : String(stripped.dropFirst(2))))
                i += 1
                continue
            }

            let indent = line.prefix(while: { $0 == " " }).count / 2
            if let text = unorderedItem(stripped) {
                blocks.append(.listItem(prefix: "•", text: text, indent: indent))
                i += 1
                continue
            }
            if let (number, text) = orderedItem(stripped) {
                blocks.append(.listItem(prefix: "\(number).", text: text, indent: indent))
                i += 1
                continue
            }

            if stripped.isEmpty {
                i += 1
                continue
            }

            var paragraph = [line]
            i += 1
            while i < lines.count {
                let next = lines[i]
                let nextStripped = next.trimmingCharacters(in: .whitespaces)
                if nextStripped.isEmpty || next.hasPrefix("#") || nextStripped.hasPrefix("```")
                    || nextStripped.hasPrefix(">") || unorderedItem(nextStripped) != nil
                    || orderedItem(nextStripped) != nil || isRule(nextStripped) {
                    break
                }
                paragraph.append(next)
                i += 1
            }
            blocks.append(.paragraph(text: paragraph.joined(separator: "\n")))
        }
        return blocks
    }

    private static func isRule(_ s: String) -> Bool {
        s == "---" || s == "***" || s == "___"
    }

    private static func unorderedItem(_ s: String) -> String? {
        for marker in ["- ", "* ", "+ "] where s.hasPrefix(marker) {
            return String(s.dropFirst(2))
        }
        return nil
    }

    private static func orderedItem(_ s: String) -> (Int, String)? {
        let digits = s.prefix(while: \.isNumber)
        guard !digits.isEmpty, let number = Int(digits) else { return nil }
        let rest = s.dropFirst(digits.count)
        guard rest.hasPrefix(". ") else { return nil }
        return (number, String(rest.dropFirst(2)).trimmingCharacters(in: .whitespaces))
    }
}
