import AppKit
import CodeBuddyKit

/// `swift run CodeBuddy`          connect to the brain on 127.0.0.1:8790
/// `swift run CodeBuddy --demo`   play every state with a fake answer, no brain needed
/// `swift run CodeBuddy --demo --snapshots DIR`   play it once, ignoring the real pointer, save
///                                                a PNG of each state in DIR, then quit
/// `swift run CodeBuddy --snapshots DIR`          brain mode; saves a PNG after every answer
///                                                (for a hint, a second one after clicking it open)
@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    /// (seconds into the demo, file name): one moment per state of DemoScript.
    static let snapshotMoments: [(TimeInterval, String)] = [
        (0.5, "1-hidden"), (2.0, "2-peek"), (5.2, "3-expanded-streaming"),
        (9.5, "4-expanded-done"), (15.0, "5-peek-after"), (20.0, "6-hidden-after"),
        (22.8, "7-hint-peek"), (25.0, "8-hint-expanded"),
    ]

    private let demo: Bool
    private let snapshotDir: URL?
    private var controller: IslandWindowController?
    private var client: BrainClient?
    private var model: NotchModel?

    init(demo: Bool, snapshotDir: URL?) {
        self.demo = demo
        self.snapshotDir = snapshotDir
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        let screen = IslandWindowController.notchScreen()
        let model = demo
            ? NotchModel(scheduler: MainQueueScheduler(), notch: IslandWindowController.geometry(of: screen),
                         expandedToPeekDelay: 6, peekToHiddenDelay: 3)
            : NotchModel(scheduler: MainQueueScheduler(), notch: IslandWindowController.geometry(of: screen))
        self.model = model
        let controller = IslandWindowController(model: model, screen: screen)
        controller.show(trackingPointer: snapshotDir == nil)
        self.controller = controller
        log("started (\(demo ? "demo" : "brain")), notch \(Int(model.notch.width))×\(Int(model.notch.height))"
            + (model.notch.hasNotch ? "" : " (no notch)"))
        observe(model)

        if demo {
            model.setConnection(.connected)
            playDemo(model, loop: snapshotDir == nil)
            if let snapshotDir { takeSnapshots(into: snapshotDir) }
        } else {
            let client = BrainClient(endpoint: .fromEnvironment())
            client.onStatus = { [weak model] status in
                model?.setConnection(status)
                log("brain \(status)")
            }
            client.onMessage = { [weak self, weak model] message in
                guard let model else { return }
                if case .answerStart(let id, let kind, _) = message { log("answer_start \(id) \(kind)") }
                model.handle(message)
                if case .answerEnd(let id, _, let first, let total) = message {
                    log("answer_end \(id) first_token_ms=\(first.map(String.init) ?? "-") total_ms=\(total)")
                    self?.snapshotAfterAnswer(id)
                }
            }
            client.start()
            self.client = client
        }
    }

    /// Plays the demo script, then loops so a person can watch it again.
    private func playDemo(_ model: NotchModel, loop: Bool) {
        let start = Date()
        for (at, step) in DemoScript.steps() {
            DispatchQueue.main.asyncAfter(deadline: .now() + at) {
                MainActor.assumeIsolated {
                    switch step {
                    case .hover(let inside): model.pointer(inside: inside)
                    case .message(let message): model.handle(message)
                    case .click: model.click()
                    }
                }
            }
        }
        log("demo: script started at \(start)")
        guard loop else { return }
        DispatchQueue.main.asyncAfter(deadline: .now() + 36) { [weak self] in
            MainActor.assumeIsolated { self?.playDemo(model, loop: true) }
        }
    }

    private func takeSnapshots(into dir: URL) {
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        for (at, name) in Self.snapshotMoments {
            DispatchQueue.main.asyncAfter(deadline: .now() + at) { [weak self] in
                MainActor.assumeIsolated {
                    guard let self, let controller = self.controller, let model = self.model else { return }
                    let url = dir.appendingPathComponent("\(name).png")
                    do {
                        try controller.snapshot(to: url)
                        log("snapshot \(url.path) (island \(model.islandState.rawValue))")
                    } catch {
                        log("snapshot failed: \(error)")
                    }
                }
            }
        }
        let last = Self.snapshotMoments.map(\.0).max() ?? 0
        DispatchQueue.main.asyncAfter(deadline: .now() + last + 0.5) { NSApp.terminate(nil) }
    }

    private func snapshotAfterAnswer(_ id: String) {
        guard let dir = snapshotDir else { return }
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) { [weak self] in
            MainActor.assumeIsolated {
                self?.snapshot(dir.appendingPathComponent("answer-\(id).png"))
                // A hint only peeks: also click it open, as a person would, and save that too.
                guard let model = self?.model, model.answers.current?.kind == .hint else { return }
                model.click()
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
                    MainActor.assumeIsolated { self?.snapshot(dir.appendingPathComponent("answer-\(id)-opened.png")) }
                }
            }
        }
    }

    private func snapshot(_ url: URL) {
        do {
            try controller?.snapshot(to: url)
            log("snapshot \(url.path) (island \(model?.islandState.rawValue ?? "?"))")
        } catch {
            log("snapshot failed: \(error)")
        }
    }

    /// Logs island transitions (handy for agents driving the app without seeing it).
    private func observe(_ model: NotchModel) {
        withObservationTracking {
            _ = model.islandState
        } onChange: { [weak self] in
            DispatchQueue.main.async {
                MainActor.assumeIsolated {
                    log("island \(model.islandState.rawValue)")
                    self?.observe(model)
                }
            }
        }
    }
}

func log(_ message: String) {
    let stamp = Date().formatted(.dateTime.hour().minute().second())
    FileHandle.standardError.write(Data("[\(stamp)] notch: \(message)\n".utf8))
}

let app = NSApplication.shared
let arguments = CommandLine.arguments
let snapshotDir = arguments.firstIndex(of: "--snapshots")
    .flatMap { arguments.indices.contains($0 + 1) ? URL(fileURLWithPath: arguments[$0 + 1]) : nil }
let delegate = AppDelegate(demo: arguments.contains("--demo"), snapshotDir: snapshotDir)
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
