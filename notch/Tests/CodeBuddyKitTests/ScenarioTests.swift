import Foundation
import Testing
@testable import CodeBuddyKit

/// The shared behaviour scenarios in `<repo>/protocol/scenarios`, also replayed by the Linux/Windows
/// overlay (`overlay/tests/test_scenarios.py`): both clients must behave the same.
private let scenarioDir = URL(fileURLWithPath: #filePath)
    .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
    .deletingLastPathComponent().appendingPathComponent("protocol/scenarios")

private let scenarioNames: [String] = {
    let files = (try? FileManager.default.contentsOfDirectory(atPath: scenarioDir.path)) ?? []
    return files.filter { $0.hasSuffix(".json") }.map { String($0.dropLast(5)) }.sorted()
}()

private let screen = IslandScreenGeometry(screenWidth: 1512, safeAreaTop: 32, auxiliaryLeftWidth: 664,
                                          auxiliaryRightWidth: 663, menuBarHeight: 32)

@MainActor
struct ScenarioTests {
    @Test func scenariosAreFound() {
        #expect(scenarioNames.count >= 10)
    }

    @Test(arguments: scenarioNames)
    func scenario(_ name: String) throws {
        let data = try Data(contentsOf: scenarioDir.appendingPathComponent("\(name).json"))
        let scenario = try #require(try JSONSerialization.jsonObject(with: data) as? [String: Any])
        let delays = scenario["delays"] as? [String: Double] ?? [:]
        let clock = ManualScheduler()
        let model = NotchModel(scheduler: clock, notch: screen,
                               expandedToPeekDelay: delays["expanded_to_peek"] ?? 20,
                               peekToHiddenDelay: delays["peek_to_hidden"] ?? 8)
        let steps = try #require(scenario["steps"] as? [[String: Any]])
        for (index, step) in steps.enumerated() {
            let at = "\(name) step \(index)"
            if let message = step["message"] {
                model.handle(BrainMessage.decode(try JSONSerialization.data(withJSONObject: message)))
            } else if let connection = step["connection"] as? String {
                switch connection {
                case "connected": model.setConnection(.connected)
                case "connecting": model.setConnection(.connecting)
                default: model.setConnection(.offline("scenario"))
                }
            } else if let pointer = step["pointer"] as? String {
                model.pointer(inside: pointer == "enter")
            } else if step["click"] != nil {
                model.click()
            } else if step["close"] != nil {
                model.close()
            } else if let seconds = step["advance"] as? Double {
                clock.advance(by: seconds)
            } else if let expected = step["expect"] as? [String: Any] {
                check(model, expected, at)
            } else {
                Issue.record("\(at): unknown step \(step)")
            }
        }
    }

    private func check(_ model: NotchModel, _ expected: [String: Any], _ at: String) {
        for (key, value) in expected {
            switch key {
            case "state":
                #expect(model.islandState.rawValue == value as? String, "\(at)")
            case "mood":
                #expect(Self.name(of: model.mood) == value as? String, "\(at)")
            case "peek_status":
                #expect(model.peekStatus == value as? String, "\(at)")
            case "preview":
                #expect(model.peekPreview == value as? String, "\(at): preview")
            case "text":
                #expect(model.answers.current?.text == value as? String, "\(at): text")
            default:
                Issue.record("\(at): unknown expectation \(key)")
            }
        }
    }

    private static func name(of mood: SproutMood) -> String {
        switch mood {
        case .idle: "idle"
        case .thinking: "thinking"
        case .happy: "happy"
        case .worried: "worried"
        }
    }
}
