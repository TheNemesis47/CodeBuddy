import Foundation
import Observation

/// How Sprout looks right now.
public enum SproutMood: Equatable, Sendable {
    case idle       // a seed, breathing
    case thinking   // sprouting while the answer streams
    case happy      // fully sprouted: answer done
    case worried    // something failed
}

/// Everything the views read. Messages and pointer events go in; island state, answer and
/// Sprout's mood come out. No AppKit, so it's tested with a manual clock.
@MainActor
@Observable
public final class NotchModel {
    public private(set) var islandState: IslandStateMachine.State = .hidden
    public private(set) var answers = AnswerStore()
    public private(set) var connection: ConnectionStatus = .connecting
    public var notch: IslandScreenGeometry

    @ObservationIgnored private let machine: IslandStateMachine

    public init(scheduler: Scheduler, notch: IslandScreenGeometry,
                expandedToPeekDelay: TimeInterval = 20, peekToHiddenDelay: TimeInterval = 8) {
        self.notch = notch
        machine = IslandStateMachine(scheduler: scheduler)
        machine.expandedToPeekDelay = expandedToPeekDelay
        machine.peekToHiddenDelay = peekToHiddenDelay
        machine.onTransition = { [weak self] _, new in self?.islandState = new }
    }

    public var layout: IslandLayout { IslandLayout(state: islandState, notch: notch) }

    public var mood: SproutMood {
        switch answers.current?.status {
        case .streaming?: .thinking
        case .done?: .happy
        case .failed?: .worried
        case nil: connection == .connected ? .idle : .worried
        }
    }

    /// One short line for the peek state's right ear.
    public var peekStatus: String {
        switch answers.current?.status {
        case .streaming?: "…"
        case .done?: "✓"
        case .failed?: "!"
        case nil:
            switch connection {
            case .connected: ""
            case .connecting: "…"
            case .offline: "off"
            }
        }
    }

    public func handle(_ message: BrainMessage) {
        switch answers.apply(message) {
        case .started(let explicit)?: machine.answerStarted(explicit: explicit)
        case .finished?: machine.answerFinished()
        case .updated?, nil: break
        }
    }

    public func setConnection(_ status: ConnectionStatus) {
        connection = status
    }

    public func pointer(inside: Bool) {
        inside ? machine.mouseEntered() : machine.mouseLeft()
    }

    public func click() { machine.click() }
    public func close() { machine.collapse() }
}
