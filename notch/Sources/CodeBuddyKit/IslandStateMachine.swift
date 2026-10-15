import Foundation

/// Pure 3-state machine for the island: hidden → peek → expanded.
/// Adapted from Coucou's island state machine (MIT, © 2026 Louis Raillé, see THIRD_PARTY.md):
/// the greeting and voice states are gone, "petit/home" became peek/expanded, timers go through
/// an injectable `Scheduler`, and answers drive the island.
@MainActor
public final class IslandStateMachine {
    public enum State: String, Equatable, Sendable {
        case hidden    // invisible: the island is exactly the notch
        case peek      // compact: notch + ears, Sprout and a one-line status
        case expanded  // panel with the answer
    }

    public private(set) var state: State = .hidden
    public private(set) var mouseInside = false

    /// Fired on every transition: (from, to).
    public var onTransition: ((State, State) -> Void)?

    /// While true (an answer is streaming), timers never collapse or hide the island.
    public var isHeldOpen = false {
        didSet {
            guard oldValue, !isHeldOpen, !mouseInside else { return }
            if state == .expanded { scheduleCollapse() }
            if state == .peek { scheduleHide() }
        }
    }

    /// expanded → peek once the pointer is away and nothing is streaming.
    public var expandedToPeekDelay: TimeInterval = 20
    /// peek → hidden.
    public var peekToHiddenDelay: TimeInterval = 8

    private let scheduler: Scheduler
    private var hideWork: ScheduledWork?
    private var collapseWork: ScheduledWork?

    public init(scheduler: Scheduler) {
        self.scheduler = scheduler
    }

    // MARK: Inputs

    public func mouseEntered() {
        mouseInside = true
        switch state {
        case .hidden:
            cancelTimers()
            transition(to: .peek)
        case .peek:
            cancel(&hideWork)
        case .expanded:
            cancel(&collapseWork)
        }
    }

    public func mouseLeft() {
        mouseInside = false
        guard !isHeldOpen else { return }
        switch state {
        case .hidden: break
        case .peek: scheduleHide()
        case .expanded: scheduleCollapse()
        }
    }

    /// A click on the island opens it from any closed state.
    public func click() {
        guard state != .expanded else { return }
        cancelTimers()
        transition(to: .expanded)
    }

    /// The close button: fold to peek right away.
    public func collapse() {
        guard state == .expanded else { return }
        cancelTimers()
        transition(to: .peek)
        if !mouseInside { scheduleHide() }
    }

    /// An explicit answer (`#?`, `#!teoria`) opens the panel; a proactive hint only peeks.
    public func answerStarted(explicit: Bool) {
        cancelTimers()
        isHeldOpen = true
        if explicit {
            transition(to: .expanded)
        } else if state == .hidden {
            transition(to: .peek)
        }
    }

    /// Streaming is over (done or failed). The island stays until the user has had time to read.
    public func answerFinished() {
        isHeldOpen = false
    }

    // MARK: Timers

    private func scheduleHide() {
        cancel(&hideWork)
        hideWork = scheduler.schedule(after: peekToHiddenDelay) { [weak self] in
            guard let self, self.state == .peek, !self.isHeldOpen, !self.mouseInside else { return }
            self.transition(to: .hidden)
        }
    }

    private func scheduleCollapse() {
        cancel(&collapseWork)
        collapseWork = scheduler.schedule(after: expandedToPeekDelay) { [weak self] in
            guard let self, self.state == .expanded, !self.isHeldOpen, !self.mouseInside else { return }
            self.transition(to: .peek)
            self.scheduleHide()
        }
    }

    private func cancelTimers() {
        cancel(&hideWork)
        cancel(&collapseWork)
    }

    private func cancel(_ work: inout ScheduledWork?) {
        work?.cancel()
        work = nil
    }

    private func transition(to new: State) {
        guard new != state else { return }
        let old = state
        state = new
        onTransition?(old, new)
    }
}
