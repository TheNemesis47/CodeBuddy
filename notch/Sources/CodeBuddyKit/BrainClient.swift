import Foundation

/// Where the brain lives and how to authenticate (SECURITY.md).
public struct BrainEndpoint: Sendable {
    public let url: URL
    public let tokenFile: URL

    public static func fromEnvironment(_ env: [String: String] = ProcessInfo.processInfo.environment) -> BrainEndpoint {
        let port = env["BUDDY_PORT"].flatMap(Int.init) ?? 8790
        let home = env["BUDDY_HOME"].map { URL(fileURLWithPath: $0) }
            ?? FileManager.default.homeDirectoryForCurrentUser
                .appendingPathComponent("Library/Application Support/CodeBuddy")
        return BrainEndpoint(url: URL(string: "ws://127.0.0.1:\(port)/ws")!,
                             tokenFile: home.appendingPathComponent("token"))
    }

    public func readToken() -> String? {
        guard let raw = try? String(contentsOf: tokenFile, encoding: .utf8) else { return nil }
        let token = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        return token.count >= 32 ? token : nil
    }
}

public enum ConnectionStatus: Equatable, Sendable {
    case connecting
    case connected
    /// The brain isn't running or refused us; we retry in the background.
    case offline(String)
}

/// Keeps one WebSocket to the brain open, reconnecting with backoff. Delivers messages on the
/// main actor. The brain may start after the notch, and the token may not exist yet: both just
/// mean "offline, retry".
@MainActor
public final class BrainClient {
    public var onMessage: ((BrainMessage) -> Void)?
    public var onStatus: ((ConnectionStatus) -> Void)?

    private let endpoint: BrainEndpoint
    private let session = URLSession(configuration: .ephemeral)
    private var task: URLSessionWebSocketTask?
    private var running = false
    private var backoff: TimeInterval = 1
    private static let maxBackoff: TimeInterval = 15
    private static let client = "codebuddy-notch/0.1.1"

    public init(endpoint: BrainEndpoint) {
        self.endpoint = endpoint
    }

    public func start() {
        guard !running else { return }
        running = true
        connect()
    }

    public func stop() {
        running = false
        task?.cancel(with: .goingAway, reason: nil)
        task = nil
    }

    private func connect() {
        guard running else { return }
        onStatus?(.connecting)
        guard let token = endpoint.readToken() else {
            retry(because: "no token yet at \(endpoint.tokenFile.path)")
            return
        }
        let task = session.webSocketTask(with: endpoint.url)
        self.task = task
        task.resume()
        // Text frame, as the protocol says (`.data` would arrive as a binary frame).
        let hello = String(decoding: BrainMessage.hello(token: token, client: Self.client), as: UTF8.self)
        task.send(.string(hello)) { [weak self] error in
            guard let error else { return }
            Task { @MainActor in self?.dropped(task, because: error.localizedDescription) }
        }
        receive(on: task)
    }

    private func receive(on task: URLSessionWebSocketTask) {
        task.receive { [weak self] result in
            Task { @MainActor in
                guard let self, self.task === task else { return }
                switch result {
                case .failure(let error):
                    self.dropped(task, because: error.localizedDescription)
                case .success(let frame):
                    let message: BrainMessage
                    switch frame {
                    case .data(let data): message = BrainMessage.decode(data)
                    case .string(let text): message = BrainMessage.decode(Data(text.utf8))
                    @unknown default: message = .ignored
                    }
                    if case .welcome = message {
                        self.backoff = 1
                        self.onStatus?(.connected)
                    }
                    self.onMessage?(message)
                    self.receive(on: task)
                }
            }
        }
    }

    private func dropped(_ task: URLSessionWebSocketTask, because reason: String) {
        guard self.task === task else { return }
        task.cancel(with: .goingAway, reason: nil)
        self.task = nil
        retry(because: reason)
    }

    private func retry(because reason: String) {
        onStatus?(.offline(reason))
        guard running else { return }
        let delay = backoff
        backoff = min(backoff * 2, Self.maxBackoff)
        DispatchQueue.main.asyncAfter(deadline: .now() + delay) { [weak self] in
            MainActor.assumeIsolated { self?.connect() }
        }
    }
}
