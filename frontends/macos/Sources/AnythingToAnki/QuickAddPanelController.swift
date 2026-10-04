import AppKit
import LauncherCore
import WebKit

/// A floating panel over the current app with the web Quick Add page.
/// It never activates the app, so the main window stays where it was and focus returns on close.
final class QuickAddPanelController: NSWindowController {
    private static let path = "quick-add"
    private static let textParameter = "text"
    private static let size = NSSize(width: 560, height: 300)
    /// The panel sits in the upper part of the screen, like Spotlight.
    private static let verticalPosition = 0.62

    private let config: AppConfig
    private let webView: WKWebView

    init(config: AppConfig) {
        self.config = config
        let closeHandler = QuickAddCloseHandler()
        let configuration = WKWebViewConfiguration()
        configuration.userContentController.add(closeHandler, contentWorld: .page, name: QuickAddCloseHandler.name)
        webView = WKWebView(frame: .zero, configuration: configuration)
        webView.isInspectable = true

        let panel = QuickAddPanel(
            contentRect: NSRect(origin: .zero, size: Self.size),
            styleMask: [.titled, .closable, .fullSizeContentView, .nonactivatingPanel],
            backing: .buffered,
            defer: true
        )
        panel.titleVisibility = .hidden
        panel.titlebarAppearsTransparent = true
        panel.isReleasedWhenClosed = false
        panel.hidesOnDeactivate = false
        panel.level = .floating
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.standardWindowButton(.miniaturizeButton)?.isHidden = true
        panel.standardWindowButton(.zoomButton)?.isHidden = true
        if let color = PageBackgroundStore().load() { panel.applyPageBackground(color) }
        panel.contentView = Self.content(webView: webView, dragStripHeight: panel.frame.height - panel.contentLayoutRect.height)
        super.init(window: panel)

        closeHandler.onClose = { [weak self] in self?.close() }
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("init(coder:) is not supported") }

    func show(text: String) {
        guard let window else { return }
        webView.load(URLRequest(url: url(for: text)))
        window.setFrameOrigin(Self.origin(for: window.frame.size))
        window.makeKeyAndOrderFront(nil)
    }

    /// The page sits under the transparent title bar and would swallow its clicks, so a native strip
    /// on top of the page drags the panel. It works even while the app is inactive.
    private static func content(webView: WKWebView, dragStripHeight: CGFloat) -> NSView {
        let container = NSView()
        let dragStrip = WindowDragView()
        for view in [webView, dragStrip] {
            view.translatesAutoresizingMaskIntoConstraints = false
            container.addSubview(view)
        }
        NSLayoutConstraint.activate([
            webView.topAnchor.constraint(equalTo: container.topAnchor),
            webView.bottomAnchor.constraint(equalTo: container.bottomAnchor),
            webView.leadingAnchor.constraint(equalTo: container.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: container.trailingAnchor),
            dragStrip.topAnchor.constraint(equalTo: container.topAnchor),
            dragStrip.leadingAnchor.constraint(equalTo: container.leadingAnchor),
            dragStrip.trailingAnchor.constraint(equalTo: container.trailingAnchor),
            dragStrip.heightAnchor.constraint(equalToConstant: dragStripHeight),
        ])
        return container
    }

    private func url(for text: String) -> URL {
        var components = URLComponents(url: config.serverURL.appendingPathComponent(Self.path), resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: Self.textParameter, value: text)]
        return components.url!
    }

    /// Opens on the screen with the mouse: that is where the text was just selected.
    private static func origin(for size: NSSize) -> NSPoint {
        let mouse = NSEvent.mouseLocation
        let screen = NSScreen.screens.first { NSMouseInRect(mouse, $0.frame, false) } ?? NSScreen.main
        guard let area = screen?.visibleFrame else { return .zero }
        return NSPoint(
            x: area.midX - size.width / 2,
            y: area.minY + (area.height - size.height) * verticalPosition
        )
    }
}

/// A non-activating panel only takes keystrokes (Esc, Enter) when it may become key.
private final class QuickAddPanel: NSPanel {
    override var canBecomeKey: Bool { true }
}

private final class WindowDragView: NSView {
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

    override func mouseDown(with event: NSEvent) {
        window?.performDrag(with: event)
    }
}

/// Answers `window.webkit.messageHandlers.closeQuickAdd.postMessage(null)` from the page.
private final class QuickAddCloseHandler: NSObject, WKScriptMessageHandler {
    static let name = "closeQuickAdd"

    var onClose: (() -> Void)?

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        onClose?()
    }
}
