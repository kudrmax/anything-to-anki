import AppKit
import LauncherCore

final class MainWindowController: NSWindowController {
    private static let frameName = "MainWindow"
    private static let defaultSize = NSSize(width: 1440, height: 900)
    private static let minimumSize = NSSize(width: 900, height: 600)

    var onRetry: (() -> Void)?

    private let webController: WebViewController
    private let statusController = StatusViewController()
    private let backgroundStore = PageBackgroundStore()
    private var status: LaunchStatus?
    private var backgroundObservation: NSKeyValueObservation?

    init(config: AppConfig) {
        webController = WebViewController(config: config)
        let window = NSWindow(
            contentRect: NSRect(origin: .zero, size: Self.defaultSize),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = ProcessInfo.processInfo.processName
        window.titleVisibility = .hidden
        window.titlebarAppearsTransparent = true
        window.isReleasedWhenClosed = false
        window.minSize = Self.minimumSize
        window.center()
        window.setFrameAutosaveName(Self.frameName)
        super.init(window: window)

        statusController.onRetry = { [weak self] in self?.onRetry?() }
        webController.onLoadFailed = { [weak self] message in
            self?.showStatus(.failed(message: "The page could not be loaded", details: message))
        }
        // The title bar takes the page's own background, so it follows the in-app theme.
        if let color = backgroundStore.load() { window.applyPageBackground(color) }
        backgroundObservation = webController.observeBackground { [weak window, backgroundStore] color in
            guard let window else { return }
            window.applyPageBackground(color)
            backgroundStore.save(color)
        }
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("init(coder:) is not supported") }

    func showStatus(_ status: LaunchStatus) {
        self.status = status
        statusController.show(status)
        setContent(statusController)
    }

    func showApp() {
        status = nil
        webController.loadApp()
        setContent(webController)
    }

    /// Cmd+R: reloads the page, retries a failed start, and does nothing while starting or stopping.
    func reload() {
        switch status {
        case nil: webController.reload()
        case .failed: onRetry?()
        case .starting, .stopping: break
        }
    }

    func zoom(_ step: PageZoom.Step) {
        webController.zoom(step)
    }

    private func setContent(_ controller: NSViewController) {
        guard let window, window.contentViewController !== controller else { return }
        let frame = window.frame
        window.contentViewController = controller
        window.setFrame(frame, display: true)
    }
}
