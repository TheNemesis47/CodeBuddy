import Foundation

/// CodeBuddy.app carries the brain in `Contents/Resources/brain/buddy`: the notch starts it on
/// launch and stops it on quit, so the user opens one app. From `swift run` there is no bundled
/// brain and nothing is started (run `buddy serve` yourself, as before).
public enum BundledBrain {
    /// The bundled brain's executable, if this app has one. `BUDDY_EXTERNAL_BRAIN=1` skips it
    /// (a brain started by hand, e.g. from the repo, on the same port).
    public static func executable(resources: URL?, environment: [String: String],
                                  fileExists: (String) -> Bool = FileManager.default.isExecutableFile) -> URL? {
        guard environment["BUDDY_EXTERNAL_BRAIN"] != "1", let resources else { return nil }
        let brain = resources.appendingPathComponent("brain").appendingPathComponent("buddy")
        return fileExists(brain.path) ? brain : nil
    }

    /// The brain's environment. An app opened from the Dock gets PATH=/usr/bin:/bin:/usr/sbin:/sbin,
    /// without the folders Claude Code installs `claude` into: add them after the inherited ones.
    public static func environment(_ base: [String: String], home: String) -> [String: String] {
        var env = base
        let extra = ["\(home)/.local/bin", "\(home)/.claude/local", "/opt/homebrew/bin", "/usr/local/bin"]
        var path = (base["PATH"] ?? "/usr/bin:/bin:/usr/sbin:/sbin").split(separator: ":").map(String.init)
        for dir in extra where !path.contains(dir) { path.append(dir) }
        env["PATH"] = path.joined(separator: ":")
        return env
    }

    /// Where the bundled brain's output goes (the app has no terminal).
    public static func logFile(home: String) -> URL {
        URL(fileURLWithPath: home).appendingPathComponent("Library/Logs/CodeBuddy/brain.log")
    }
}
