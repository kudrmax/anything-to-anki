import AppKit

/// Receives the text selected in any app when its Services menu item is chosen.
/// The selector is the `NSMessage` of the `NSServices` entry in Info.plist.
final class QuickAddService: NSObject {
    var onText: ((String) -> Void)?

    @objc func addToAnki(
        _ pasteboard: NSPasteboard,
        userData: String?,
        error: AutoreleasingUnsafeMutablePointer<NSString?>
    ) {
        guard let text = pasteboard.string(forType: .string),
              !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        else {
            error.pointee = "No text is selected"
            return
        }
        onText?(text)
    }
}
