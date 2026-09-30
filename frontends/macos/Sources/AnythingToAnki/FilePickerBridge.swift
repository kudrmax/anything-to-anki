import AppKit
import UniformTypeIdentifiers
import WebKit

/// Answers `window.webkit.messageHandlers.pickFile.postMessage({extensions})` with an absolute path,
/// so the page can hand the backend a path instead of uploading the file.
final class FilePickerBridge: NSObject, WKScriptMessageHandlerWithReply {
    static let name = "pickFile"

    private weak var window: NSWindow?
    private let isAppFrame: (WKFrameInfo) -> Bool

    /// Only the app's own top-level page may ask for paths; embedded frames get nil.
    init(isAppFrame: @escaping (WKFrameInfo) -> Bool) {
        self.isAppFrame = isAppFrame
    }

    func attach(to window: NSWindow?) {
        self.window = window
    }

    func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage,
        replyHandler: @escaping (Any?, String?) -> Void
    ) {
        guard isAppFrame(message.frameInfo) else { return replyHandler(nil, nil) }
        let body = message.body as? [String: Any]
        let extensions = body?["extensions"] as? [String] ?? []

        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        let types = extensions.compactMap { UTType(filenameExtension: $0) }
        if !types.isEmpty { panel.allowedContentTypes = types }

        let finish: (NSApplication.ModalResponse) -> Void = { response in
            replyHandler(response == .OK ? panel.url?.path : nil, nil)
        }
        if let window {
            panel.beginSheetModal(for: window, completionHandler: finish)
        } else {
            finish(panel.runModal())
        }
    }
}
