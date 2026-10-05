import AppKit

/// A monochrome take on the app icon: lines of text with the target bar highlighted.
/// It is a template image, so the menu bar tints it like the system icons.
enum MenuBarIcon {
    private struct Bar {
        let x: CGFloat
        let width: CGFloat
        let row: Int
        let isTarget: Bool
    }

    private static let size = NSSize(width: 18, height: 18)
    private static let barHeight: CGFloat = 2.6
    private static let rowGap: CGFloat = 2
    private static let contextAlpha: CGFloat = 0.45
    private static let bars = [
        Bar(x: 1, width: 16, row: 0, isTarget: false),
        Bar(x: 1, width: 4.6, row: 1, isTarget: false),
        Bar(x: 6.6, width: 7, row: 1, isTarget: true),
        Bar(x: 14.6, width: 2.4, row: 1, isTarget: false),
        Bar(x: 1, width: 10, row: 2, isTarget: false),
    ]

    static func make(accessibilityDescription: String) -> NSImage {
        let image = NSImage(size: size, flipped: true) { _ in
            let rows = CGFloat((bars.map(\.row).max() ?? 0) + 1)
            let top = (size.height - rows * barHeight - (rows - 1) * rowGap) / 2
            for bar in bars {
                let y = top + CGFloat(bar.row) * (barHeight + rowGap)
                let rect = NSRect(x: bar.x, y: y, width: bar.width, height: barHeight)
                NSColor.black.withAlphaComponent(bar.isTarget ? 1 : contextAlpha).setFill()
                NSBezierPath(roundedRect: rect, xRadius: barHeight / 2, yRadius: barHeight / 2).fill()
            }
            return true
        }
        image.isTemplate = true
        image.accessibilityDescription = accessibilityDescription
        return image
    }
}
