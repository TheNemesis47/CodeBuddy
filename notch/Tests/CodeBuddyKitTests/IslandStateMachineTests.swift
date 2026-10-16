import Testing
@testable import CodeBuddyKit

@MainActor
struct IslandStateMachineTests {
    let clock = ManualScheduler()
    let machine: IslandStateMachine

    init() {
        machine = IslandStateMachine(scheduler: clock)
        machine.expandedToPeekDelay = 20
        machine.peekToHiddenDelay = 8
    }

    @Test func hoverPeeksAndLeavingHidesAfterTheDelay() {
        machine.mouseEntered()
        #expect(machine.state == .peek)
        machine.mouseLeft()
        clock.advance(by: 7.9)
        #expect(machine.state == .peek)
        clock.advance(by: 0.2)
        #expect(machine.state == .hidden)
    }

    @Test func comingBackCancelsTheHide() {
        machine.mouseEntered()
        machine.mouseLeft()
        clock.advance(by: 5)
        machine.mouseEntered()
        clock.advance(by: 60)
        #expect(machine.state == .peek)
    }

    @Test func clickExpandsAndLeavingFoldsToPeekThenHides() {
        machine.mouseEntered()
        machine.click()
        #expect(machine.state == .expanded)
        machine.mouseLeft()
        clock.advance(by: 20)
        #expect(machine.state == .peek)
        clock.advance(by: 8)
        #expect(machine.state == .hidden)
    }

    @Test func clickFromHiddenOpens() {
        machine.click()
        #expect(machine.state == .expanded)
    }

    @Test func explicitAnswerOpensAndStaysOpenWhileStreaming() {
        machine.answerStarted(explicit: true)
        machine.answerHasContent()
        #expect(machine.state == .expanded)
        machine.mouseEntered()
        machine.mouseLeft()
        clock.advance(by: 600)
        #expect(machine.state == .expanded)
        machine.answerFinished()
        clock.advance(by: 20)
        #expect(machine.state == .peek)
        clock.advance(by: 8)
        #expect(machine.state == .hidden)
    }

    @Test func pointerInsideWhenTheAnswerEndsKeepsItOpenUntilItLeaves() {
        machine.answerStarted(explicit: true)
        machine.answerHasContent()
        machine.mouseEntered()
        machine.answerFinished()
        clock.advance(by: 120)
        #expect(machine.state == .expanded)
        machine.mouseLeft()
        clock.advance(by: 20)
        #expect(machine.state == .peek)
    }

    @Test func explicitAnswerPeeksUntilItsFirstToken() {
        machine.answerStarted(explicit: true)
        #expect(machine.state == .peek)
        #expect(machine.isWaitingToOpen)
        clock.advance(by: 30)  // Claude is slow today: still a peek, never hidden, never an empty panel
        #expect(machine.state == .peek)
        machine.answerHasContent()
        #expect(machine.state == .expanded)
        machine.collapse()
        machine.answerHasContent()  // later tokens don't reopen a panel the user closed
        #expect(machine.state == .peek)
    }

    @Test func aClickWhileWaitingOpensOnce() {
        machine.answerStarted(explicit: true)
        machine.click()
        #expect(machine.state == .expanded)
        #expect(!machine.isWaitingToOpen)
    }

    @Test func hintOnlyPeeks() {
        machine.answerStarted(explicit: false)
        #expect(machine.state == .peek)
        clock.advance(by: 600)
        #expect(machine.state == .peek)
        machine.answerFinished()
        clock.advance(by: 8)
        #expect(machine.state == .hidden)
    }

    @Test func hintDoesNotShrinkAnOpenPanel() {
        machine.click()
        machine.answerStarted(explicit: false)
        #expect(machine.state == .expanded)
    }

    @Test func closeFoldsRightAway() {
        machine.click()
        machine.collapse()
        #expect(machine.state == .peek)
        clock.advance(by: 8)
        #expect(machine.state == .hidden)
    }

    @Test func transitionsAreReported() {
        var seen: [String] = []
        machine.onTransition = { old, new in seen.append("\(old.rawValue)→\(new.rawValue)") }
        machine.mouseEntered()
        machine.click()
        machine.click()  // already expanded: no transition
        machine.collapse()
        #expect(seen == ["hidden→peek", "peek→expanded", "expanded→peek"])
    }
}
