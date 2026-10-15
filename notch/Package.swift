// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "CodeBuddy",
    platforms: [.macOS(.v14)],
    targets: [
        // Pure logic: state machine, geometry, protocol, markdown, brain client. No AppKit views.
        .target(name: "CodeBuddyKit"),
        // The app: notch panel, SwiftUI views, Sprout.
        .executableTarget(name: "CodeBuddy", dependencies: ["CodeBuddyKit"]),
        .testTarget(name: "CodeBuddyKitTests", dependencies: ["CodeBuddyKit"]),
    ]
)
