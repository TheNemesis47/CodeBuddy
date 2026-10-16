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
        #expect(model.islandState == .peek)  // nothing to read yet: Sprout thinks in the peek
        #expect(model.mood == .thinking)
        model.handle(.answerDelta(id: "a", text: ""))
        #expect(model.islandState == .peek)  // an empty delta is not a token
        model.handle(.answerDelta(id: "a", text: "Perché…"))
        #expect(model.islandState == .expanded)
        #expect(model.layout == IslandLayout(state: .expanded, notch: notch))
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

    @Test func aHintPeeksWithAPreviewAndOpensOnClick() {
        model.handle(.answerStart(id: "h", kind: .hint, title: "load.py:6"))
        #expect(model.islandState == .peek)  // a hint never opens the panel by itself
        #expect(model.peekPreview == "…")
        model.handle(.answerDelta(id: "h", text: "Guarda la riga 6: **chi chiude** il file `f`?"))
        #expect(model.peekPreview == "Guarda la riga 6: chi chiude il file f?")
        #expect(model.layout == IslandLayout(state: .peek, notch: notch, preview: true))
        model.handle(.answerEnd(id: "h", model: "qwen", firstTokenMs: 400, totalMs: 900))
        clock.advance(by: 7)
        #expect(model.islandState == .peek)
        model.click()
        #expect(model.islandState == .expanded)
        #expect(model.answers.current?.text.contains("chi chiude") == true)
    }

    @Test func aHintThatIsNotOpenedHidesAfterThePeekDelay() {
        model.handle(.answerStart(id: "h", kind: .hint, title: "t"))
        model.handle(.answerDelta(id: "h", text: "x"))
        model.handle(.answerEnd(id: "h", model: "qwen", firstTokenMs: 1, totalMs: 2))
        clock.advance(by: 8)
        #expect(model.islandState == .hidden)
    }

    @Test func explicitAnswersAndFailedHintsHaveNoPreview() {
        model.handle(.answerStart(id: "a", kind: .question, title: "q"))
        model.handle(.answerDelta(id: "a", text: "Perché…"))
        #expect(model.peekPreview == nil)
        model.handle(.answerStart(id: "h", kind: .hint, title: "t"))
        model.handle(.error(id: "h", message: "local engine: HTTP 500"))
        #expect(model.peekPreview == nil)
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
                case .click: model.click()
                }
            }
        }
        var t = 0.0
        var answerBeforeHint: String?
        while t < 40 {
            clock.advance(by: 0.05)
            t += 0.05
            if states.last != model.islandState { states.append(model.islandState) }
            if answerBeforeHint == nil, t >= 20 { answerBeforeHint = model.answers.current?.text }
            if abs(t - 23) < 0.01 { #expect(model.peekPreview?.hasPrefix("Alla riga 6") == true) }
        }
        // question: peek on hover, expanded, folds, hides; hint: peek, click → expanded, folds, hides
        #expect(states == [.hidden, .peek, .expanded, .peek, .hidden, .peek, .expanded, .peek, .hidden])
        #expect(answerBeforeHint == DemoScript.answer)
        #expect(model.answers.current?.text == DemoScript.hint)
        #expect(model.answers.current?.kind == .hint)
        #expect(model.mood == .happy)
    }

    @Test func chunksReassemble() {
        #expect(DemoScript.chunks(of: "abcdefg", size: 3) == ["abc", "def", "g"])
    }
}
