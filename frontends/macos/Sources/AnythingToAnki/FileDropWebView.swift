import AppKit
import WebKit

/// Hands files dropped on the app's page to it as absolute paths in a `nativefiledrop` event,
/// because a browser drop exposes only the file contents and the backend reads sources from disk.
/// The page decides where a drop is allowed through its `dragover` handling, as on the web.
final class FileDropWebView: WKWebView {
    static let event = "nativefiledrop"

    var isAppPage: () -> Bool = { false }

    override func performDragOperation(_ sender: NSDraggingInfo) -> Bool {
        let paths = Self.filePaths(on: sender.draggingPasteboard)
        guard !paths.isEmpty, isAppPage() else { return super.performDragOperation(sender) }
        // Ends the drag for the page as if the file left it, so nothing stays highlighted.
        super.draggingExited(sender)
        callAsyncJavaScript(
            "window.dispatchEvent(new CustomEvent(name, { detail: paths }))",
            arguments: ["name": Self.event, "paths": paths],
            in: nil,
            in: .page
        )
        return true
    }

    private static func filePaths(on pasteboard: NSPasteboard) -> [String] {
        let urls = pasteboard.readObjects(forClasses: [NSURL.self], options: [.urlReadingFileURLsOnly: true]) as? [URL]
        return urls?.map(\.path) ?? []
    }
}
