import Foundation

public struct LaunchPolicy: Sendable {
    public let pollInterval: Duration
    public let attempts: Int
    public let outputTailLines: Int

    public init(pollInterval: Duration, attempts: Int, outputTailLines: Int) {
        self.pollInterval = pollInterval
        self.attempts = attempts
        self.outputTailLines = outputTailLines
    }

    public static let standard = LaunchPolicy(pollInterval: .milliseconds(500), attempts: 240, outputTailLines: 40)
}

public enum LaunchOutcome: Equatable, Sendable {
    case ready
    case failed(message: String, outputTail: String)
}

/// Brings the local server up through `make`, and takes it down on exit only if it started it.
public actor ServerLauncher {
    static let upCommand = "make up"
    static let downCommand = "make down"

    private let projectDir: URL
    private let probe: HealthProbe
    private let runner: CommandRunner
    private let sleeper: Sleeper
    private let policy: LaunchPolicy
    private var ownsProcesses = false

    public init(projectDir: URL, probe: HealthProbe, runner: CommandRunner, sleeper: Sleeper, policy: LaunchPolicy) {
        self.projectDir = projectDir
        self.probe = probe
        self.runner = runner
        self.sleeper = sleeper
        self.policy = policy
    }

    public func start() async -> LaunchOutcome {
        if await probe.isUp() { return .ready }

        ownsProcesses = true
        let result = await runner.run(Self.upCommand, in: projectDir)
        guard result.exitCode == 0 else {
            return .failed(message: "`\(Self.upCommand)` exited with code \(result.exitCode)", outputTail: tail(of: result.output))
        }

        for _ in 0..<policy.attempts {
            if await probe.isUp() { return .ready }
            await sleeper.sleep(for: policy.pollInterval)
        }
        return .failed(message: "The server did not answer after `\(Self.upCommand)`", outputTail: tail(of: result.output))
    }

    public func stop() async {
        guard ownsProcesses else { return }
        _ = await runner.run(Self.downCommand, in: projectDir)
        ownsProcesses = false
    }

    private func tail(of output: String) -> String {
        output
            .split(separator: "\n", omittingEmptySubsequences: false)
            .suffix(policy.outputTailLines)
            .joined(separator: "\n")
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }
}
