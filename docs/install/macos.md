# CodeBuddy on macOS

The Mac uses the Swift notch, built from source (no packaged build yet). Needs macOS 14+, Xcode,
`uv`, and the Claude Code CLI logged in.

```sh
cd brain && uv run buddy serve            # terminal 1: the brain
cd notch && swift run CodeBuddy           # terminal 2: the notch
```

Plugin: `cd ide-pycharm && ./gradlew buildPlugin`, then in PyCharm: Settings → Plugins → ⚙ →
*Install Plugin from Disk…* → `ide-pycharm/build/distributions/codebuddy-pycharm-0.1.2.zip`. More in
`docs/development.md`.
