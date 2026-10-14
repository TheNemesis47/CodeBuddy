import Foundation

/// `--demo`: every state with a fake streamed answer, no brain needed.
public enum DemoStep: Equatable, Sendable {
    case hover(Bool)              // pointer enters / leaves the notch
    case message(BrainMessage)    // as if the brain had sent it
}

public enum DemoScript {
    public static let answerID = "demo-1"

    static let answer = """
    Alla riga 6 `open(path)` crea un file che **nessuno chiude**: lo passi a `json.load`, \
    che lo legge ma non lo chiude.

    - In CPython si chiude "per caso" quando il garbage collector lo elimina.
    - Se `json.load` fallisce, il file può restare aperto.

    Usa un context manager:

    ```python
    with open(path) as f:
        data = json.load(f)
    ```

    Il file si chiude all'uscita dal blocco, anche in caso di errore.
    """

    /// (seconds from start, step). Timings leave room for screenshots of each state.
    public static func steps(chunkSize: Int = 12) -> [(at: TimeInterval, step: DemoStep)] {
        var steps: [(TimeInterval, DemoStep)] = [
            (1.0, .hover(true)),   // hidden → peek
            (3.0, .hover(false)),
            (4.0, .message(.answerStart(id: answerID, kind: .question,
                                        title: "perché non chiude il file?"))),  // → expanded
        ]
        var t: TimeInterval = 4.5
        for chunk in chunks(of: answer, size: chunkSize) {
            steps.append((t, .message(.answerDelta(id: answerID, text: chunk))))
            t += 0.06
        }
        steps.append((t + 0.2, .message(.answerEnd(id: answerID, model: "demo", firstTokenMs: 500,
                                                   totalMs: Int((t - 4.0) * 1000)))))
        return steps
    }

    static func chunks(of text: String, size: Int) -> [String] {
        var result: [String] = []
        var index = text.startIndex
        while index < text.endIndex {
            let end = text.index(index, offsetBy: size, limitedBy: text.endIndex) ?? text.endIndex
            result.append(String(text[index..<end]))
            index = end
        }
        return result
    }
}
