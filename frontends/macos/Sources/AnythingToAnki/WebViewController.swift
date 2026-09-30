import AppKit
import LauncherCore
import WebKit

final class WebViewController: NSViewController {
    var onLoadFailed: ((String) -> Void)?

    private let config: AppConfig
    private let filePicker = FilePickerBridge()
    private lazy var webView: WKWebView = makeWebView()

    init(config: AppConfig) {
        self.config = config
        super.init(nibName: nil, bundle: nil)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("init(coder:) is not supported") }

    override func loadView() {
        view = webView
    }

    override func viewDidAppear() {
        super.viewDidAppear()
        filePicker.attach(to: view.window)
    }

    func loadApp() {
        loadViewIfNeeded()
        if webView.url.map(config.isAppURL) == true { return }
        webView.load(URLRequest(url: config.serverURL))
    }

    func reload() {
        webView.reload()
    }

    func observeBackground(_ apply: @escaping (NSColor) -> Void) -> NSKeyValueObservation {
        loadViewIfNeeded()
        return webView.observe(\.underPageBackgroundColor, options: [.new]) { webView, _ in
            guard webView.url != nil else { return }
            apply(webView.underPageBackgroundColor)
        }
    }

    private func makeWebView() -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.mediaTypesRequiringUserActionForPlayback = []
        configuration.preferences.isElementFullscreenEnabled = true
        configuration.userContentController.addScriptMessageHandler(filePicker, contentWorld: .page, name: FilePickerBridge.name)
        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.allowsBackForwardNavigationGestures = true
        webView.isInspectable = true
        return webView
    }

    private func openExternally(_ url: URL) {
        NSWorkspace.shared.open(url)
    }
}

extension WebViewController: WKNavigationDelegate {
    func webView(
        _ webView: WKWebView,
        decidePolicyFor navigationAction: WKNavigationAction,
        decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
    ) {
        guard let url = navigationAction.request.url,
              navigationAction.targetFrame?.isMainFrame != false,
              !config.isAppURL(url),
              url.scheme != "about", url.scheme != "blob", url.scheme != "data"
        else { return decisionHandler(.allow) }
        openExternally(url)
        decisionHandler(.cancel)
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        onLoadFailed?(error.localizedDescription)
    }

    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        webView.reload()
    }
}

extension WebViewController: WKUIDelegate {
    func webView(
        _ webView: WKWebView,
        createWebViewWith configuration: WKWebViewConfiguration,
        for navigationAction: WKNavigationAction,
        windowFeatures: WKWindowFeatures
    ) -> WKWebView? {
        if let url = navigationAction.request.url { openExternally(url) }
        return nil
    }

    func webView(
        _ webView: WKWebView,
        runOpenPanelWith parameters: WKOpenPanelParameters,
        initiatedByFrame frame: WKFrameInfo,
        completionHandler: @escaping ([URL]?) -> Void
    ) {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        panel.canChooseDirectories = parameters.allowsDirectories
        panel.canChooseFiles = true
        guard let window = view.window else { return completionHandler(nil) }
        panel.beginSheetModal(for: window) { response in
            completionHandler(response == .OK ? panel.urls : nil)
        }
    }

    func webView(
        _ webView: WKWebView,
        runJavaScriptAlertPanelWithMessage message: String,
        initiatedByFrame frame: WKFrameInfo,
        completionHandler: @escaping () -> Void
    ) {
        presentAlert(message, buttons: ["OK"]) { _ in completionHandler() }
    }

    func webView(
        _ webView: WKWebView,
        runJavaScriptConfirmPanelWithMessage message: String,
        initiatedByFrame frame: WKFrameInfo,
        completionHandler: @escaping (Bool) -> Void
    ) {
        presentAlert(message, buttons: ["OK", "Cancel"]) { completionHandler($0 == .alertFirstButtonReturn) }
    }

    private func presentAlert(_ message: String, buttons: [String], completion: @escaping (NSApplication.ModalResponse) -> Void) {
        let alert = NSAlert()
        alert.messageText = message
        buttons.forEach { alert.addButton(withTitle: $0) }
        guard let window = view.window else { return completion(alert.runModal()) }
        alert.beginSheetModal(for: window, completionHandler: completion)
    }
}
