import XCTest
@testable import LauncherCore

final class PickRequestTests: XCTestCase {
    func testOneFileByDefault() {
        let request = PickRequest(body: ["extensions": ["srt"]])

        XCTAssertFalse(request.multiple)
        XCTAssertEqual(request.extensions, ["srt"])
        XCTAssertEqual(request.reply(paths: ["/m/a.srt"], accepted: true) as? String, "/m/a.srt")
    }

    func testSeveralFilesReplyWithAllPaths() {
        let request = PickRequest(body: ["multiple": true])

        XCTAssertTrue(request.multiple)
        XCTAssertEqual(request.reply(paths: ["/a/1.txt", "/a/2.txt"], accepted: true) as? [String], ["/a/1.txt", "/a/2.txt"])
    }

    func testCancelledPickRepliesNothing() {
        XCTAssertNil(PickRequest(body: nil).reply(paths: ["/a/1.txt"], accepted: false))
        XCTAssertEqual(PickRequest(body: ["multiple": true]).reply(paths: [], accepted: false) as? [String], [])
    }
}
