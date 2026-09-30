import AppKit
import LauncherCore

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private var launcher: ServerLauncher?
    private var windowController: MainWindowController?

    func applicationDidFinishLaunching(_ notification: Notification) {
        let config: AppConfig
        do {
            config = try AppConfig(infoDictionary: Bundle.main.infoDictionary ?? [:])
        } catch {
            showFatalError(error)
            return
        }

        NSApp.mainMenu = MainMenu.build(appName: ProcessInfo.processInfo.processName)
        launcher = ServerLauncher(
            projectDir: config.projectDir,
            probe: HTTPHealthProbe(url: config.serverURL),
            runner: LoginShellRunner(),
            sleeper: TaskSleeper(),
            policy: .standard
        )
        let controller = MainWindowController(config: config)
        controller.onRetry = { [weak self] in self?.launch() }
        windowController = controller
        controller.showWindow(nil)
        NSApp.activate(ignoringOtherApps: true)
        launch()
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard let launcher else { return .terminateNow }
        windowController?.showStatus(.stopping)
        Task {
            await launcher.stop()
            NSApp.reply(toApplicationShouldTerminate: true)
        }
        return .terminateLater
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag { windowController?.showWindow(nil) }
        return true
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }

    @objc func reloadPage(_ sender: Any?) {
        windowController?.reload()
    }

    private func launch() {
        guard let launcher, let windowController else { return }
        windowController.showStatus(.starting)
        Task {
            let outcome = await launcher.start()
            switch outcome {
            case .ready:
                windowController.showApp()
            case let .failed(message, outputTail):
                windowController.showStatus(.failed(message: message, details: outputTail))
            }
        }
    }

    private func showFatalError(_ error: Error) {
        let alert = NSAlert()
        alert.messageText = "This app bundle is broken"
        alert.informativeText = "\(error)\n\nRebuild it with `make app` in the project folder."
        alert.runModal()
        NSApp.terminate(nil)
    }
}
