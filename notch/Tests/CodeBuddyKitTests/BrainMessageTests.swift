import Foundation
import Testing
@testable import CodeBuddyKit

/// The protocol examples in `<repo>/protocol/examples` are the contract with the brain.
private let examples = URL(fileURLWithPath: #filePath)
    .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
    .deletingLastPathComponent().appendingPathComponent("protocol/examples")

private func example(_ name: String) throws -> Data {
    try Data(contentsOf: examples.appendingPathComponent("\(name).json"))
}

struct BrainMessageTests {
    @Test func decodesEveryBrainToNotchExample() throws {
        #expect(BrainMessage.decode(try example("welcome")) == .welcome(brain: "0.1.0"))
        #expect(BrainMessage.decode(try example("answer_start")) ==
            .answerStart(id: "7f1c2e9a-0b1d-4c8e-9f00-1a2b3c4d5e6f", kind: .question,
                         title: "perché non chiude il file?"))
        #expect(BrainMessage.decode(try example("answer_delta")) ==
            .answerDelta(id: "7f1c2e9a-0b1d-4c8e-9f00-1a2b3c4d5e6f",
                         text: "`open(path)` restituisce un file che nessuno chiude: "))
        #expect(BrainMessage.decode(try example("answer_end")) ==
            .answerEnd(id: "7f1c2e9a-0b1d-4c8e-9f00-1a2b3c4d5e6f", model: "claude-sonnet-5-5",
                       firstTokenMs: 1930, totalMs: 2590))
        #expect(BrainMessage.decode(try example("error")) == .error(id: nil, message: "invalid hello"))
    }

    @Test func ideMessagesAndUnknownsAreIgnored() throws {
        #expect(BrainMessage.decode(try example("trigger.question")) == .ignored)
        #expect(BrainMessage.decode(Data(#"{"v":0,"type":"future_thing"}"#.utf8)) == .ignored)
        #expect(BrainMessage.decode(Data(#"{"v":1,"type":"welcome","brain":"9"}"#.utf8)) == .ignored)
        #expect(BrainMessage.decode(Data("not json".utf8)) == .ignored)
        #expect(BrainMessage.decode(Data(#"{"v":0,"type":"answer_start","id":"x","kind":"alt","title":""}"#.utf8)) == .ignored)
    }

    @Test func helloHasTheSameShapeAsTheProtocolExample() throws {
        let ours = try JSONSerialization.jsonObject(with: BrainMessage.hello(token: "t", client: "c")) as? [String: Any]
        let reference = try JSONSerialization.jsonObject(with: try example("hello.notch")) as? [String: Any]
        #expect(Set(ours?.keys ?? [:].keys) == Set(reference?.keys ?? [:].keys))
        #expect(ours?["role"] as? String == "notch")
        #expect(ours?["v"] as? Int == 0)
        #expect(ours?["type"] as? String == "hello")
    }

    @Test func endpointReadsPortAndTokenFromTheEnvironment() throws {
        let home = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: home, withIntermediateDirectories: true)
        let endpoint = BrainEndpoint.fromEnvironment(["BUDDY_PORT": "8799", "BUDDY_HOME": home.path])
        #expect(endpoint.url.absoluteString == "ws://127.0.0.1:8799/ws")
        #expect(endpoint.readToken() == nil)
        try "short\n".write(to: endpoint.tokenFile, atomically: true, encoding: .utf8)
        #expect(endpoint.readToken() == nil)
        let token = String(repeating: "a", count: 64)
        try "\(token)\n".write(to: endpoint.tokenFile, atomically: true, encoding: .utf8)
        #expect(endpoint.readToken() == token)
    }
}
