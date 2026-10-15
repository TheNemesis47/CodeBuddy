import Foundation

/// A cancellable delayed action. Lets the state machine run on real time in the app and on a
/// manual clock in tests.
@MainActor
public protocol Scheduler: AnyObject {
    func schedule(after seconds: TimeInterval, _ action: @escaping @MainActor () -> Void) -> ScheduledWork
}

@MainActor
public final class ScheduledWork {
    private var cancelled = false
    private let onCancel: () -> Void

    public init(onCancel: @escaping () -> Void = {}) { self.onCancel = onCancel }

    public var isCancelled: Bool { cancelled }

    public func cancel() {
        guard !cancelled else { return }
        cancelled = true
        onCancel()
    }
}

/// Real time, on the main queue.
@MainActor
public final class MainQueueScheduler: Scheduler {
    public init() {}

    public func schedule(after seconds: TimeInterval, _ action: @escaping @MainActor () -> Void) -> ScheduledWork {
        let work = ScheduledWork()
        DispatchQueue.main.asyncAfter(deadline: .now() + seconds) {
            MainActor.assumeIsolated {
                if !work.isCancelled { action() }
            }
        }
        return work
    }
}

/// Test clock: nothing runs until `advance(by:)`.
@MainActor
public final class ManualScheduler: Scheduler {
    private struct Entry {
        let due: TimeInterval
        let work: ScheduledWork
        let action: @MainActor () -> Void
    }

    public private(set) var now: TimeInterval = 0
    private var entries: [Entry] = []

    public init() {}

    public var pendingCount: Int { entries.filter { !$0.work.isCancelled }.count }

    public func schedule(after seconds: TimeInterval, _ action: @escaping @MainActor () -> Void) -> ScheduledWork {
        let work = ScheduledWork()
        entries.append(Entry(due: now + seconds, work: work, action: action))
        return work
    }

    public func advance(by seconds: TimeInterval) {
        let target = now + seconds
        while let next = entries.enumerated()
            .filter({ !$0.element.work.isCancelled && $0.element.due <= target })
            .min(by: { $0.element.due < $1.element.due }) {
            entries.remove(at: next.offset)
            now = next.element.due
            next.element.action()
        }
        now = target
        entries.removeAll { $0.work.isCancelled }
    }
}
