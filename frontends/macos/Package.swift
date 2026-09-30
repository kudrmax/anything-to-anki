// swift-tools-version:5.10
import PackageDescription

let package = Package(
    name: "AnythingToAnki",
    platforms: [.macOS(.v13)],
    targets: [
        .target(name: "LauncherCore"),
        .executableTarget(name: "AnythingToAnki", dependencies: ["LauncherCore"]),
        .testTarget(name: "LauncherCoreTests", dependencies: ["LauncherCore"]),
    ]
)
