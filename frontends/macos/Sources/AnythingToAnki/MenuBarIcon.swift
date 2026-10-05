import AppKit

/// A monochrome take on the app icon: a rounded square with lines of text cut out of it,
/// the target bar cut through and the rest only dimmed.
/// It is a template image, so the menu bar tints it like the system icons.
enum MenuBarIcon {
    private struct Bar {
        let x: CGFloat
        let width: CGFloat
        let row: Int
        let isTarget: Bool
    }

    private static let size = NSSize(width: 18, height: 18)
    private static let tile = NSRect(x: 1, y: 1, width: 16, height: 16)
    private static let tileRadius: CGFloat = 4
    private static let barHeight: CGFloat = 1.8
    private static let rowGap: CGFloat = 1.5
    private static let contextCutout: CGFloat = 0.55
    private static let bars = [
        Bar(x: 3.5, width: 11, row: 0, isTarget: false),
        Bar(x: 3.5, width: 2.6, row: 1, isTarget: false),
        Bar(x: 7, width: 4.8, row: 1, isTarget: true),
        Bar(x: 12.7, width: 1.8, row: 1, isTarget: false),
        Bar(x: 3.5, width: 6.5, row: 2, isTarget: false),
    ]

    static func make(accessibilityDescription: String) -> NSImage {
        let image = NSImage(size: size, flipped: true) { _ in
            NSColor.black.setFill()
            NSBezierPath(roundedRect: tile, xRadius: tileRadius, yRadius: tileRadius).fill()
            guard let context = NSGraphicsContext.current else { return true }
            context.compositingOperation = .destinationOut
            let rows = CGFloat((bars.map(\.row).max() ?? 0) + 1)
            let top = tile.midY - (rows * barHeight + (rows - 1) * rowGap) / 2
            for bar in bars {
                let y = top + CGFloat(bar.row) * (barHeight + rowGap)
                let rect = NSRect(x: bar.x, y: y, width: bar.width, height: barHeight)
                NSColor.black.withAlphaComponent(bar.isTarget ? 1 : contextCutout).setFill()
                NSBezierPath(roundedRect: rect, xRadius: barHeight / 2, yRadius: barHeight / 2).fill()
            }
            return true
        }
        image.isTemplate = true
        image.accessibilityDescription = accessibilityDescription
        return image
    }
}
