import Testing
@testable import CodeBuddyKit

private let notch = IslandScreenGeometry(screenWidth: 1512, safeAreaTop: 32, auxiliaryLeftWidth: 664,
                                         auxiliaryRightWidth: 663, menuBarHeight: 32)

@MainActor
struct NotchModelTests {
    let clock = ManualScheduler()
    let model: NotchModel

    init() {
        model = NotchModel(scheduler: clock, notch: notch, expandedToPeekDelay: 20, peekToHiddenDelay: 8)
        model.setConnection(.connected)
    }

    @Test func aQuestionOpensStreamsAndThenFolds() {
        #expect(model.mood == .idle)
        model.handle(.answerStart(id: "a", kind: .question, title: "perché?"))
        #expect(model.islandState == .expanded)
        #expect(model.mood == .thinking)
        #expect(model.layout == IslandLayout(state: .expanded, notch: notch))
        model.handle(.answerDelta(id: "a", text: "Perché…"))
        clock.advance(by: 300)
        #expect(model.islandState == .expanded)  // still streaming
        model.handle(.answerEnd(id: "a", model: "m", firstTokenMs: 1, totalMs: 2))
        #expect(model.mood == .happy)
        #expect(model.peekStatus == "✓")
        clock.advance(by: 20)
        #expect(model.islandState == .peek)
        clock.advance(by: 8)
        #expect(model.islandState == .hidden)
    }

    @Test func aFailedAnswerReleasesTheIslandAndWorriesSprout() {
        model.handle(.answerStart(id: "a", kind: .theory, title: "t"))
        model.handle(.error(id: "a", message: "claude: quota"))
        #expect(model.mood == .worried)
        #expect(model.peekStatus == "!")
        clock.advance(by: 28)
        #expect(model.islandState == .hidden)
    }

    @Test func staleMessagesDoNotMoveTheIsland() {
        model.handle(.answerDelta(id: "ghost", text: "x"))
        model.handle(.answerEnd(id: "ghost", model: "m", firstTokenMs: nil, totalMs: 1))
        #expect(model.islandState == .hidden)
        #expect(model.answers.current == nil)
    }

    @Test func offlineBrainShowsInThePeek() {
        model.setConnection(.offline("connection refused"))
        #expect(model.mood == .worried)
        #expect(model.peekStatus == "off")
    }

    @Test func pointerAndButtons() {
        model.pointer(inside: true)
        #expect(model.islandState == .peek)
        model.click()
        #expect(model.islandState == .expanded)
        model.close()
        #expect(model.islandState == .peek)
    }
}

@MainActor
struct DemoScriptTests {
    /// Replays `--demo` on a manual clock with the demo's own delays.
    @Test func demoPlaysEveryStateAndTheWholeAnswer() {
        let clock = ManualScheduler()
        let model = NotchModel(scheduler: clock, notch: notch, expandedToPeekDelay: 6, peekToHiddenDelay: 3)
        var states: [IslandStateMachine.State] = [model.islandState]
        for (at, step) in DemoScript.steps() {
            _ = clock.schedule(after: at) {
                switch step {
                case .hover(let inside): model.pointer(inside: inside)
                case .message(let message): model.handle(message)
                }
            }
        }
        var t = 0.0
        while t < 30 {
            clock.advance(by: 0.05)
            t += 0.05
            if states.last != model.islandState { states.append(model.islandState) }
        }
        #expect(states == [.hidden, .peek, .expanded, .peek, .hidden])
        #expect(model.answers.current?.text == DemoScript.answer)
        #expect(model.mood == .happy)
    }

    @Test func chunksReassemble() {
        #expect(DemoScript.chunks(of: "abcdefg", size: 3) == ["abc", "def", "g"])
    }
}
