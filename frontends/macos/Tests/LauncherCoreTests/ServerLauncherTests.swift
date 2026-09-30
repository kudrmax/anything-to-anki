import XCTest
@testable import LauncherCore

final class ServerLauncherTests: XCTestCase {
    private let projectDir = URL(fileURLWithPath: "/tmp/project")

    func testUsesRunningServerWithoutStartingIt() async {
        let probe = FakeProbe(upAfter: 0)
        let runner = FakeRunner()
        let launcher = makeLauncher(probe: probe, runner: runner)

        let outcome = await launcher.start()

        XCTAssertEqual(outcome, .ready)
        XCTAssertEqual(runner.commands, [])
    }

    func testStartsServerWhenItIsDown() async {
        let probe = FakeProbe(upAfter: 3)
        let runner = FakeRunner()
        let launcher = makeLauncher(probe: probe, runner: runner)

        let outcome = await launcher.start()

        XCTAssertEqual(outcome, .ready)
        XCTAssertEqual(runner.commands, ["make up"])
        XCTAssertEqual(runner.directories, [projectDir])
    }

    func testReportsFailedStartWithOutputTail() async {
        let probe = FakeProbe(upAfter: nil)
        let output = (1...50).map { "line \($0)" }.joined(separator: "\n")
        let runner = FakeRunner(results: ["make up": CommandResult(exitCode: 2, output: output)])
        let launcher = makeLauncher(probe: probe, runner: runner)

        let outcome = await launcher.start()

        guard case let .failed(message, tail) = outcome else { return XCTFail("expected failure, got \(outcome)") }
        XCTAssertTrue(message.contains("make up"))
        XCTAssertTrue(tail.hasSuffix("line 50"))
        XCTAssertFalse(tail.contains("line 1\n"))
    }

    func testReportsTimeoutWhenServerNeverAnswers() async {
        let probe = FakeProbe(upAfter: nil)
        let launcher = makeLauncher(probe: probe, runner: FakeRunner())

        let outcome = await launcher.start()

        guard case .failed = outcome else { return XCTFail("expected failure, got \(outcome)") }
    }

    func testStopsOnlyProcessesItStarted() async {
        let runner = FakeRunner()
        let launcher = makeLauncher(probe: FakeProbe(upAfter: 1), runner: runner)

        _ = await launcher.start()
        await launcher.stop()

        XCTAssertEqual(runner.commands, ["make up", "make down"])
    }

    func testLeavesForeignProcessesRunning() async {
        let runner = FakeRunner()
        let launcher = makeLauncher(probe: FakeProbe(upAfter: 0), runner: runner)

        _ = await launcher.start()
        await launcher.stop()

        XCTAssertEqual(runner.commands, [])
    }

    func testStopsProcessesStartedEvenIfServerNeverCameUp() async {
        let runner = FakeRunner()
        let launcher = makeLauncher(probe: FakeProbe(upAfter: nil), runner: runner)

        _ = await launcher.start()
        await launcher.stop()

        XCTAssertEqual(runner.commands, ["make up", "make down"])
    }

    private func makeLauncher(probe: FakeProbe, runner: FakeRunner) -> ServerLauncher {
        ServerLauncher(
            projectDir: projectDir,
            probe: probe,
            runner: runner,
            sleeper: InstantSleeper(),
            policy: LaunchPolicy(pollInterval: .milliseconds(1), attempts: 10, outputTailLines: 20)
        )
    }
}

private final class FakeProbe: HealthProbe, @unchecked Sendable {
    private let upAfter: Int?
    private var calls = 0

    init(upAfter: Int?) { self.upAfter = upAfter }

    func isUp() async -> Bool {
        defer { calls += 1 }
        guard let upAfter else { return false }
        return calls >= upAfter
    }
}

private final class FakeRunner: CommandRunner, @unchecked Sendable {
    private let results: [String: CommandResult]
    private(set) var commands: [String] = []
    private(set) var directories: [URL] = []

    init(results: [String: CommandResult] = [:]) { self.results = results }

    func run(_ command: String, in directory: URL) async -> CommandResult {
        commands.append(command)
        directories.append(directory)
        return results[command] ?? CommandResult(exitCode: 0, output: "")
    }
}

private struct InstantSleeper: Sleeper {
    func sleep(for duration: Duration) async {}
}
