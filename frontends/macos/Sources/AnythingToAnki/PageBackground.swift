import AppKit

extension NSWindow {
    /// Window chrome and native text follow the page's light or dark background.
    func applyPageBackground(_ color: NSColor) {
        backgroundColor = color
        let brightness = color.usingColorSpace(.sRGB)?.brightnessComponent ?? 0
        appearance = NSAppearance(named: brightness < 0.5 ? .darkAqua : .aqua)
    }
}
