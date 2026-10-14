import Testing
@testable import CodeBuddyKit

struct AnswerStoreTests {
    @Test func startDeltaEnd() {
        var store = AnswerStore()
        #expect(store.apply(.answerStart(id: "a", kind: .theory, title: "t")) == .started(explicit: true))
        #expect(store.apply(.answerDelta(id: "a", text: "Ciao ")) == .updated)
        #expect(store.apply(.answerDelta(id: "a", text: "mondo")) == .updated)
        #expect(store.apply(.answerEnd(id: "a", model: "m", firstTokenMs: 10, totalMs: 20)) == .finished)
        #expect(store.current?.text == "Ciao mondo")
        #expect(store.current?.status == .done(model: "m", firstTokenMs: 10, totalMs: 20))
    }

    @Test func hintsAreNotExplicit() {
        var store = AnswerStore()
        #expect(store.apply(.answerStart(id: "h", kind: .hint, title: "")) == .started(explicit: false))
    }

    @Test func messagesForOtherOrFinishedAnswersAreDropped() {
        var store = AnswerStore()
        _ = store.apply(.answerStart(id: "a", kind: .question, title: "q"))
        #expect(store.apply(.answerDelta(id: "old", text: "x")) == nil)
        _ = store.apply(.answerEnd(id: "a", model: "m", firstTokenMs: nil, totalMs: 1))
        #expect(store.apply(.answerDelta(id: "a", text: "late")) == nil)
        #expect(store.apply(.answerEnd(id: "a", model: "m", firstTokenMs: nil, totalMs: 2)) == nil)
        #expect(store.current?.text == "")
    }

    @Test func aNewAnswerReplacesTheOldOne() {
        var store = AnswerStore()
        _ = store.apply(.answerStart(id: "a", kind: .question, title: "q"))
        _ = store.apply(.answerDelta(id: "a", text: "vecchio"))
        _ = store.apply(.answerStart(id: "b", kind: .question, title: "q2"))
        #expect(store.current?.id == "b")
        #expect(store.current?.text == "")
    }

    @Test func errorsWithAnIdFailTheAnswerOthersBecomeANotice() {
        var store = AnswerStore()
        _ = store.apply(.answerStart(id: "a", kind: .question, title: "q"))
        #expect(store.apply(.error(id: "a", message: "quota")) == .finished)
        #expect(store.current?.status == .failed("quota"))
        #expect(store.apply(.error(id: nil, message: "invalid")) == .updated)
        #expect(store.notice == "invalid")
        #expect(store.apply(.welcome(brain: "1")) == nil)
    }
}
