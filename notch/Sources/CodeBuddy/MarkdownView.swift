import AppKit
import CodeBuddyKit
import SwiftUI

/// Renders an answer's markdown, block by block, while it streams.
/// Adapted from Coucou's chat markdown view (MIT, © 2026 Louis Raillé, see THIRD_PARTY.md).
struct MarkdownView: View {
    let markdown: String

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            ForEach(Array(Markdown.parse(markdown).enumerated()), id: \.offset) { _, block in
                blockView(block)
            }
        }
        .environment(\.openURL, OpenURLAction { url in
            guard ["http", "https"].contains(url.scheme?.lowercased() ?? "") else { return .discarded }
            NSWorkspace.shared.open(url)
            return .handled
        })
    }

    @ViewBuilder
    private func blockView(_ block: MarkdownBlock) -> some View {
        switch block {
        case let .heading(level, text):
            Text(inline(text))
                .font(.system(size: level <= 2 ? 14 : 13, weight: level <= 2 ? .bold : .semibold))
                .foregroundStyle(Palette.heading)
                .fixedSize(horizontal: false, vertical: true)
                .textSelection(.enabled)

        case let .paragraph(text):
            Text(inline(text))
                .font(.system(size: 12.5))
                .foregroundStyle(Palette.body)
                .fixedSize(horizontal: false, vertical: true)
                .textSelection(.enabled)

        case let .codeBlock(_, code, _):
            HStack(alignment: .top) {
                Text(code)
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(Palette.code)
                    .fixedSize(horizontal: false, vertical: true)
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
                CopyButton(text: code)
            }
            .padding(10)
            .background(Palette.codeBackground)
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .overlay(RoundedRectangle(cornerRadius: 8).stroke(.white.opacity(0.08), lineWidth: 1))

        case let .listItem(prefix, text, indent):
            HStack(alignment: .top, spacing: 6) {
                Text(prefix)
                    .font(.system(size: 12.5))
                    .foregroundStyle(Palette.muted)
                    .frame(minWidth: prefix.count > 2 ? 20 : 10, alignment: .leading)
                Text(inline(text))
                    .font(.system(size: 12.5))
                    .foregroundStyle(Palette.body)
                    .fixedSize(horizontal: false, vertical: true)
                    .textSelection(.enabled)
            }
            .padding(.leading, CGFloat(indent) * 12)

        case let .quote(text):
            HStack(alignment: .top, spacing: 8) {
                Capsule().fill(Palette.muted).frame(width: 2)
                Text(inline(text))
                    .font(.system(size: 12.5))
                    .foregroundStyle(Palette.quote)
                    .fixedSize(horizontal: false, vertical: true)
                    .textSelection(.enabled)
            }

        case .rule:
            Divider().opacity(0.3)
        }
    }

    private func inline(_ text: String) -> AttributedString {
        var options = AttributedString.MarkdownParsingOptions(interpretedSyntax: .inlineOnlyPreservingWhitespace)
        options.failurePolicy = .returnPartiallyParsedIfPossible
        return (try? AttributedString(markdown: text, options: options)) ?? AttributedString(text)
    }
}

private struct CopyButton: View {
    let text: String
    @State private var copied = false

    var body: some View {
        Button {
            NSPasteboard.general.clearContents()
            NSPasteboard.general.setString(text, forType: .string)
            withAnimation { copied = true }
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                withAnimation { copied = false }
            }
        } label: {
            Image(systemName: copied ? "checkmark" : "doc.on.doc")
                .font(.system(size: 10))
                .foregroundStyle(copied ? Palette.success : Palette.muted)
        }
        .buttonStyle(.plain)
        .frame(width: 22, height: 22)
        .background(.white.opacity(0.06))
        .clipShape(RoundedRectangle(cornerRadius: 4))
        .accessibilityLabel(copied ? "Copied" : "Copy code")
    }
}

enum Palette {
    static let heading = Color(red: 0.945, green: 0.949, blue: 0.957)
    static let body = Color(red: 0.69, green: 0.71, blue: 0.745)
    static let code = Color(red: 0.784, green: 0.804, blue: 0.831)
    static let codeBackground = Color(red: 0.051, green: 0.055, blue: 0.071)
    static let muted = Color(red: 0.42, green: 0.44, blue: 0.475)
    static let quote = Color(red: 0.54, green: 0.56, blue: 0.596)
    static let success = Color(red: 0.133, green: 0.773, blue: 0.369)
    static let leaf = SproutDrawing.leaf
    static let warning = Color(red: 0.98, green: 0.6, blue: 0.25)
}
