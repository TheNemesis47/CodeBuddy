import Foundation

public struct Answer: Equatable, Sendable {
    public enum Status: Equatable, Sendable {
        case streaming
        case done(model: String, firstTokenMs: Int?, totalMs: Int)
        case failed(String)
    }

    public let id: String
    public let kind: AnswerKind
    public let title: String
    public var text: String
    public var status: Status

    public var isStreaming: Bool { status == .streaming }
}

/// What the UI should do after a message was applied.
public enum AnswerEvent: Equatable, Sendable {
    case started(explicit: Bool)
    case updated
    case finished
}

/// The answer on screen. Only one at a time: a new answer_start replaces the old one, and
/// deltas for any other id are dropped.
public struct AnswerStore: Equatable, Sendable {
    public private(set) var current: Answer?
    /// A brain-level problem not tied to an answer (e.g. an invalid message).
    public private(set) var notice: String?

    public init() {}

    public mutating func apply(_ message: BrainMessage) -> AnswerEvent? {
        switch message {
        case let .answerStart(id, kind, title):
            current = Answer(id: id, kind: kind, title: title, text: "", status: .streaming)
            notice = nil
            return .started(explicit: kind.isExplicit)
        case let .answerDelta(id, text):
            guard current?.id == id, current?.isStreaming == true else { return nil }
            current?.text += text
            return .updated
        case let .answerEnd(id, model, firstTokenMs, totalMs):
            guard current?.id == id, current?.isStreaming == true else { return nil }
            current?.status = .done(model: model, firstTokenMs: firstTokenMs, totalMs: totalMs)
            return .finished
        case let .error(id, text):
            if let id {
                guard current?.id == id, current?.isStreaming == true else { return nil }
                current?.status = .failed(text)
                return .finished
            }
            notice = text
            return .updated
        case .welcome, .ignored:
            return nil
        }
    }
}
