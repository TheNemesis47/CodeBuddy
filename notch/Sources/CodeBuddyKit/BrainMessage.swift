import Foundation

/// brain → notch messages from protocol v0 (`protocol/schemas`). Anything else decodes to
/// `.ignored`, so a newer brain never crashes an older notch.
public enum BrainMessage: Equatable, Sendable {
    case welcome(brain: String)
    case answerStart(id: String, kind: AnswerKind, title: String)
    case answerDelta(id: String, text: String)
    case answerEnd(id: String, model: String, firstTokenMs: Int?, totalMs: Int)
    case error(id: String?, message: String)
    case ignored

    public static let protocolVersion = 0

    public static func decode(_ data: Data) -> BrainMessage {
        guard let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              object["v"] as? Int == protocolVersion,
              let type = object["type"] as? String else { return .ignored }
        let id = object["id"] as? String
        switch type {
        case "welcome":
            return .welcome(brain: object["brain"] as? String ?? "?")
        case "answer_start":
            guard let id, let kind = (object["kind"] as? String).flatMap(AnswerKind.init) else { return .ignored }
            return .answerStart(id: id, kind: kind, title: object["title"] as? String ?? "")
        case "answer_delta":
            guard let id, let text = object["text"] as? String else { return .ignored }
            return .answerDelta(id: id, text: text)
        case "answer_end":
            guard let id else { return .ignored }
            return .answerEnd(id: id, model: object["model"] as? String ?? "",
                              firstTokenMs: object["first_token_ms"] as? Int,
                              totalMs: object["total_ms"] as? Int ?? 0)
        case "error":
            return .error(id: id, message: object["message"] as? String ?? "error")
        default:
            return .ignored
        }
    }

    /// The first frame the notch sends (protocol `hello`, role notch).
    public static func hello(token: String, client: String) -> Data {
        let object: [String: Any] = ["v": protocolVersion, "type": "hello", "role": "notch",
                                     "token": token, "client": client]
        // A dictionary of strings and ints always serializes.
        return (try? JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])) ?? Data()
    }
}

public enum AnswerKind: String, Sendable {
    case question, theory, hint, review

    /// Explicit requests open the panel; a proactive hint and the review after a save only peek.
    public var isExplicit: Bool { self == .question || self == .theory }
}
