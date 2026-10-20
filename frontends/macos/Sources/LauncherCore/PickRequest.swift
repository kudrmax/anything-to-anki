import Foundation

/// What the page asked the file picker for: allowed extensions and whether several files may be picked.
public struct PickRequest {
    public let extensions: [String]
    public let multiple: Bool

    public init(body: Any?) {
        let fields = body as? [String: Any]
        extensions = fields?["extensions"] as? [String] ?? []
        multiple = fields?["multiple"] as? Bool ?? false
    }

    /// One path, or nil when cancelled; for several files — every path, empty when cancelled.
    public func reply(paths: [String], accepted: Bool) -> Any? {
        if multiple { return accepted ? paths : [String]() }
        return accepted ? paths.first : nil
    }
}
