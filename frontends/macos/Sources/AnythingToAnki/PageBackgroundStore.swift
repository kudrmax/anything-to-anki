import AppKit

/// Remembers the page background, so the window opens in the app's colours before the page loads.
struct PageBackgroundStore {
    private static let key = "PageBackgroundColor"

    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    func load() -> NSColor? {
        guard let data = defaults.data(forKey: Self.key) else { return nil }
        return try? NSKeyedUnarchiver.unarchivedObject(ofClass: NSColor.self, from: data)
    }

    func save(_ color: NSColor) {
        guard let data = try? NSKeyedArchiver.archivedData(withRootObject: color, requiringSecureCoding: true) else { return }
        defaults.set(data, forKey: Self.key)
    }
}
