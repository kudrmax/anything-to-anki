import AppKit

/// The menu bar icon that keeps the app reachable while its window is closed and it is out of the Dock.
@MainActor
final class StatusBarController {
    private static let symbolName = "rectangle.stack"

    private let statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)

    init(appName: String, target: AppDelegate) {
        if let button = statusItem.button {
            let image = NSImage(systemSymbolName: Self.symbolName, accessibilityDescription: appName)
            image?.isTemplate = true
            button.image = image
            button.toolTip = appName
        }
        let menu = NSMenu()
        let open = NSMenuItem(title: "Open \(appName)", action: #selector(AppDelegate.openMainWindow(_:)), keyEquivalent: "")
        open.target = target
        let quit = NSMenuItem(title: "Quit \(appName)", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "")
        quit.target = NSApp
        menu.addItem(open)
        menu.addItem(.separator())
        menu.addItem(quit)
        statusItem.menu = menu
    }
}
