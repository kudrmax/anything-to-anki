import AppKit
import LauncherCore

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private var launcher: ServerLauncher?
    private var windowController: MainWindowController?
    private var quickAddPanel: QuickAddPanelController?
    private let quickAddService = QuickAddService()
    private var pendingQuickAddText: String?
    private var isServerReady = false
    private var isTerminating = false

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
        quickAddPanel = QuickAddPanelController(config: config)
        quickAddService.onText = { [weak self] text in self?.quickAdd(text) }
        NSApp.servicesProvider = quickAddService
        controller.showWindow(nil)
        NSApp.activate(ignoringOtherApps: true)
        launch()
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard let launcher else { return .terminateNow }
        if isTerminating { return .terminateLater }
        isTerminating = true
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

    @objc func zoomIn(_ sender: Any?) {
        windowController?.zoom(.zoomIn)
    }

    @objc func zoomOut(_ sender: Any?) {
        windowController?.zoom(.zoomOut)
    }

    @objc func resetZoom(_ sender: Any?) {
        windowController?.zoom(.reset)
    }

    /// A selection sent while the server is still starting opens once it is up.
    private func quickAdd(_ text: String) {
        guard isServerReady else {
            pendingQuickAddText = text
            return
        }
        quickAddPanel?.show(text: text)
    }

    private func launch() {
        guard let launcher, let windowController, !isTerminating else { return }
        isServerReady = false
        windowController.showStatus(.starting)
        Task {
            let outcome = await launcher.start()
            guard !isTerminating else { return }
            switch outcome {
            case .ready:
                isServerReady = true
                windowController.showApp()
                if let text = pendingQuickAddText {
                    pendingQuickAddText = nil
                    quickAddPanel?.show(text: text)
                }
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
