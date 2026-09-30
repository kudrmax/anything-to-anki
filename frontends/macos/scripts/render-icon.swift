// Renders Resources/AppIcon.png: a phrase with one highlighted target, in the web UI palette.
// Run once after changing the design: swift scripts/render-icon.swift Resources/AppIcon.png
import AppKit

let canvas: CGFloat = 1024
let tileInset: CGFloat = 100
let tileRadius: CGFloat = 185
let contentInset: CGFloat = 150
let lineHeight: CGFloat = 56
let lineStep: CGFloat = 102
let wordGap: CGFloat = 30

let background = NSColor(srgbRed: 0x10 / 255, green: 0x0f / 255, blue: 0x0e / 255, alpha: 1)
let surface = NSColor(srgbRed: 0x22 / 255, green: 0x21 / 255, blue: 0x20 / 255, alpha: 1)
let text = NSColor(srgbRed: 0xe9 / 255, green: 0xe8 / 255, blue: 0xe7 / 255, alpha: 0.28)
let accent = NSColor(srgbRed: 0xed / 255, green: 0xa5 / 255, blue: 0x7c / 255, alpha: 1)

let output = CommandLine.arguments.dropFirst().first ?? "AppIcon.png"
let image = NSImage(size: NSSize(width: canvas, height: canvas), flipped: true) { _ in
    let tile = NSRect(x: tileInset, y: tileInset, width: canvas - 2 * tileInset, height: canvas - 2 * tileInset)
    let tilePath = NSBezierPath(roundedRect: tile, xRadius: tileRadius, yRadius: tileRadius)
    NSGradient(starting: surface, ending: background)!.draw(in: tilePath, angle: 90)

    NSGraphicsContext.saveGraphicsState()
    tilePath.addClip()
    let glow = NSGradient(starting: accent.withAlphaComponent(0.22), ending: accent.withAlphaComponent(0))!
    glow.draw(fromCenter: NSPoint(x: tile.minX, y: tile.minY), radius: 0,
              toCenter: NSPoint(x: tile.minX, y: tile.minY), radius: tile.width * 0.8, options: [])
    NSGraphicsContext.restoreGraphicsState()

    let left = tile.minX + contentInset
    let width = tile.width - 2 * contentInset
    let firstY = tile.midY - lineStep - lineHeight / 2

    func bar(_ x: CGFloat, _ row: Int, _ w: CGFloat, _ color: NSColor, glow: Bool = false) {
        let rect = NSRect(x: x, y: firstY + CGFloat(row) * lineStep, width: w, height: lineHeight)
        NSGraphicsContext.saveGraphicsState()
        if glow {
            let shadow = NSShadow()
            shadow.shadowColor = accent.withAlphaComponent(0.7)
            shadow.shadowBlurRadius = 60
            shadow.set()
        }
        color.setFill()
        NSBezierPath(roundedRect: rect, xRadius: lineHeight / 2, yRadius: lineHeight / 2).fill()
        NSGraphicsContext.restoreGraphicsState()
    }

    bar(left, 0, width, text)
    let before: CGFloat = 150
    let target: CGFloat = 230
    bar(left, 1, before, text)
    bar(left + before + wordGap, 1, target, accent, glow: true)
    bar(left + before + target + 2 * wordGap, 1, width - before - target - 2 * wordGap, text)
    bar(left, 2, width * 0.62, text)
    return true
}

let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(canvas), pixelsHigh: Int(canvas),
                              bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                              colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
image.draw(in: NSRect(x: 0, y: 0, width: canvas, height: canvas))
NSGraphicsContext.restoreGraphicsState()
try! bitmap.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: output))
