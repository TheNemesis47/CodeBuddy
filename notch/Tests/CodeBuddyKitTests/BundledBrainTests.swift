import Foundation
import Testing
@testable import CodeBuddyKit

struct BundledBrainTests {
    let resources = URL(fileURLWithPath: "/Applications/CodeBuddy.app/Contents/Resources")

    @Test func theAppStartsTheBrainItCarries() {
        let found = BundledBrain.executable(resources: resources, environment: [:]) { _ in true }
        #expect(found?.path == "/Applications/CodeBuddy.app/Contents/Resources/brain/buddy")
    }

    @Test func swiftRunHasNoBundledBrainAndAHandStartedOneWins() {
        #expect(BundledBrain.executable(resources: resources, environment: [:]) { _ in false } == nil)
        #expect(BundledBrain.executable(resources: nil, environment: [:]) { _ in true } == nil)
        #expect(BundledBrain.executable(resources: resources, environment: ["BUDDY_EXTERNAL_BRAIN": "1"]) { _ in true } == nil)
    }

    @Test func theDocksShortPathGetsClaudesFolders() {
        let env = BundledBrain.environment(["PATH": "/usr/bin:/bin", "BUDDY_PORT": "8791"], home: "/Users/me")
        #expect(env["PATH"] == "/usr/bin:/bin:/Users/me/.local/bin:/Users/me/.claude/local:/opt/homebrew/bin:/usr/local/bin")
        #expect(env["BUDDY_PORT"] == "8791")
        let already = BundledBrain.environment(["PATH": "/opt/homebrew/bin:/usr/bin"], home: "/Users/me")
        #expect(already["PATH"]?.components(separatedBy: "/opt/homebrew/bin").count == 2)  // not twice
    }
}
