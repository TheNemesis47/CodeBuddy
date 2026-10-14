import AppKit
import CodeBuddyKit
import SwiftUI

/// A borderless, non-activating panel that sits over the notch, above the menu bar, on every
/// Space. It ignores the mouse except over the island, so the menu bar stays clickable.
/// Adapted from Coucou's island panel and window controller (MIT, see THIRD_PARTY.md).
final class IslandPanel: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }

    /// Let the panel sit in the menu bar / notch area: don't let macOS push it down.
    override func constrainFrameRect(_ frameRect: NSRect, to screen: NSScreen?) -> NSRect {
        frameRect
    }
}

@MainActor
final class IslandWindowController {
    static let panelSize = CGSize(width: 720, height: 560)
    /// Extra hover margin around the island, in points.
    static let hoverMargin: CGFloat = 6

    let panel: IslandPanel
    private let model: NotchModel
    private var mouseTimer: Timer?
    private var pointerInside = false

    init(model: NotchModel, screen: NSScreen) {
        self.model = model
        let frame = Self.panelFrame(on: screen)
        panel = IslandPanel(contentRect: frame, styleMask: [.borderless, .nonactivatingPanel],
                            backing: .buffered, defer: false)
        panel.backgroundColor = .clear
        panel.isOpaque = false
        panel.hasShadow = false
        panel.level = NSWindow.Level(rawValue: Int(CGWindowLevelForKey(.mainMenuWindow)) + 3)
        panel.collectionBehavior = [.canJoinAllSpaces, .stationary, .fullScreenAuxiliary, .ignoresCycle]
        panel.ignoresMouseEvents = true
        panel.contentView = NSHostingView(rootView: IslandView(model: model))
        panel.setFrame(frame, display: true)
    }

    /// Saves what the panel shows right now as a PNG. Renders the view itself, so it needs no
    /// Screen Recording permission (the desktop behind the island isn't included).
    func snapshot(to url: URL) throws {
        guard let view = panel.contentView,
              let rep = view.bitmapImageRepForCachingDisplay(in: view.bounds) else { return }
        view.cacheDisplay(in: view.bounds, to: rep)
        guard let png = rep.representation(using: .png, properties: [:]) else { return }
        try png.write(to: url)
    }

    func show(trackingPointer: Bool = true) {
        panel.orderFrontRegardless()
        guard trackingPointer else { return }
        // Poll the pointer (as the original does): global monitors miss moves over our panel, and
        // a tracking area can't see the pointer while the panel ignores mouse events.
        mouseTimer = Timer.scheduledTimer(withTimeInterval: 1.0 / 30, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { self?.trackPointer() }
        }
    }

    private func trackPointer() {
        let layout = model.layout
        let frame = panel.frame
        let island = CGRect(x: frame.midX - layout.width / 2, y: frame.maxY - layout.height,
                            width: layout.width, height: layout.height)
        // Without a notch, the resting bar must not steal clicks from the window below.
        let hoverRect = model.notch.hasNotch || model.islandState == .expanded
            ? island.insetBy(dx: -Self.hoverMargin, dy: -Self.hoverMargin) : island
        let inside = hoverRect.contains(NSEvent.mouseLocation)
        if panel.ignoresMouseEvents == inside { panel.ignoresMouseEvents = !inside }
        if inside != pointerInside {
            pointerInside = inside
            model.pointer(inside: inside)
        }
    }

    static func panelFrame(on screen: NSScreen) -> NSRect {
        let sf = screen.frame
        return NSRect(x: sf.midX - panelSize.width / 2, y: sf.maxY - panelSize.height,
                      width: panelSize.width, height: panelSize.height)
    }

    /// The screen with a notch if there is one, else the main screen.
    static func notchScreen() -> NSScreen {
        NSScreen.screens.first { $0.safeAreaInsets.top > 0 } ?? NSScreen.main ?? NSScreen.screens[0]
    }

    static func geometry(of screen: NSScreen) -> IslandScreenGeometry {
        IslandScreenGeometry(
            screenWidth: screen.frame.width, safeAreaTop: screen.safeAreaInsets.top,
            auxiliaryLeftWidth: screen.auxiliaryTopLeftArea?.width,
            auxiliaryRightWidth: screen.auxiliaryTopRightArea?.width,
            menuBarHeight: screen.frame.maxY - screen.visibleFrame.maxY)
    }
}
