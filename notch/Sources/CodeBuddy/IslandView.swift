import CodeBuddyKit
import SwiftUI

/// The island, centred at the top of a transparent panel.
struct IslandView: View {
    let model: NotchModel

    var body: some View {
        let layout = model.layout
        VStack(spacing: 0) {
            ZStack(alignment: .top) {
                IslandShape(width: layout.width, height: layout.height,
                            cornerRadius: layout.cornerRadius, topRadius: layout.topRadius)
                    .fill(.black)
                content(layout)
                    .frame(width: layout.width, height: layout.height, alignment: .top)
                    .clipShape(IslandShape(width: layout.width, height: layout.height,
                                           cornerRadius: layout.cornerRadius, topRadius: layout.topRadius))
            }
            .frame(width: layout.width, height: layout.height)
            // On a screen without a notch, the hidden island must really disappear.
            .opacity(model.islandState == .hidden && !model.notch.hasNotch ? 0 : 1)
            .contentShape(Rectangle())
            .onTapGesture { model.click() }
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .animation(.spring(response: 0.42, dampingFraction: 0.82), value: model.islandState)
    }

    @ViewBuilder
    private func content(_ layout: IslandLayout) -> some View {
        switch model.islandState {
        case .hidden:
            EmptyView()
        case .peek:
            PeekContent(model: model)
                .transition(.opacity)
        case .expanded:
            ExpandedContent(model: model)
                .transition(.opacity.combined(with: .scale(scale: 0.96, anchor: .top)))
        }
    }
}

/// Notch + ears: Sprout in the left ear, a one-character status in the right one. A hint adds
/// its opening words on a line under the notch; a click opens the whole hint.
private struct PeekContent: View {
    let model: NotchModel

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 0) {
                SproutView(mood: model.mood, size: max(16, model.notch.height - 8))
                    .frame(width: IslandLayout.earWidth, alignment: .center)
                Spacer(minLength: model.notch.width)
                Text(model.peekStatus)
                    .font(.system(size: 12, weight: .semibold, design: .rounded))
                    .foregroundStyle(statusColor)
                    .frame(width: IslandLayout.earWidth, alignment: .center)
            }
            .frame(height: model.notch.height)
            if let preview = model.peekPreview {
                Text(preview)
                    .font(.system(size: 12.5))
                    .foregroundStyle(Palette.body)
                    .lineLimit(1)
                    .truncationMode(.tail)
                    .padding(.horizontal, 18)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .accessibilityLabel("Suggerimento: \(preview). Clicca per aprirlo.")
            }
        }
    }

    private var statusColor: Color {
        switch model.mood {
        case .happy: Palette.success
        case .worried: Palette.warning
        default: Palette.body
        }
    }
}

private struct ExpandedContent: View {
    let model: NotchModel

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Color.clear.frame(height: model.notch.height)  // the physical notch sits here
            header
            Divider().overlay(.white.opacity(0.08))
            answer
            footer
        }
    }

    private var header: some View {
        HStack(spacing: 10) {
            SproutView(mood: model.mood, size: 30)
            VStack(alignment: .leading, spacing: 1) {
                Text(kindLabel)
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(Palette.leaf)
                    .textCase(.uppercase)
                Text(model.answers.current?.title ?? "CodeBuddy")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(Palette.heading)
                    .lineLimit(1)
            }
            Spacer()
            Button { model.close() } label: {
                Image(systemName: "chevron.up")
                    .font(.system(size: 11, weight: .bold))
                    .foregroundStyle(Palette.muted)
                    .frame(width: 24, height: 24)
                    .background(.white.opacity(0.06), in: Circle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Close")
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 10)
    }

    private var answer: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading) {
                    if let current = model.answers.current {
                        MarkdownView(markdown: current.text.isEmpty ? "…" : current.text)
                    } else {
                        Text(idleText)
                            .font(.system(size: 12.5))
                            .foregroundStyle(Palette.body)
                    }
                    Color.clear.frame(height: 1).id("bottom")
                }
                .padding(.horizontal, 18)
                .padding(.vertical, 12)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .onChange(of: model.answers.current?.text) { _, _ in
                if model.answers.current?.isStreaming == true { proxy.scrollTo("bottom", anchor: .bottom) }
            }
        }
    }

    private var footer: some View {
        Text(footerText)
            .font(.system(size: 10.5, design: .monospaced))
            .foregroundStyle(Palette.muted)
            .lineLimit(1)
            .padding(.horizontal, 18)
            .padding(.bottom, 12)
            .padding(.top, 4)
    }

    private var kindLabel: String {
        switch model.answers.current?.kind {
        case .question?: "domanda"
        case .theory?: "teoria"
        case .hint?: "suggerimento"
        case nil: "CodeBuddy"
        }
    }

    private var idleText: String {
        switch model.connection {
        case .connected: "Scrivi `#? domanda` o `#!teoria argomento` nel codice."
        case .connecting: "Mi collego al brain…"
        case .offline: "Il brain non è attivo: avvialo con `uv run buddy serve`."
        }
    }

    private var footerText: String {
        if let notice = model.answers.notice { return notice }
        switch model.answers.current?.status {
        case .streaming?: return "sto scrivendo…"
        case let .done(answerModel, firstTokenMs, totalMs)?:
            let first = firstTokenMs.map { "\($0) ms" } ?? "—"
            return "\(answerModel) · primo token \(first) · totale \(totalMs) ms"
        case let .failed(message)?: return "errore: \(message)"
        case nil:
            if case let .offline(reason) = model.connection { return reason }
            return ""
        }
    }
}
