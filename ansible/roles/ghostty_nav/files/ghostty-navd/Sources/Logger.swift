import Foundation

let ghosttyNavLogPath = FileManager.default.homeDirectoryForCurrentUser
    .appendingPathComponent(".local/state/ghostty-nav/ghostty-navd.log")
    .path

let ghosttyNavMaxLogBytes: UInt64 = 1_048_576

func ensureParentDirectory(for path: String, mode: Int = 0o700) throws {
    let parent = URL(fileURLWithPath: path).deletingLastPathComponent().path
    try FileManager.default.createDirectory(atPath: parent, withIntermediateDirectories: true)
    chmod(parent, mode_t(mode))
}

func truncateLogIfNeeded() {
    guard let attrs = try? FileManager.default.attributesOfItem(atPath: ghosttyNavLogPath),
          let size = attrs[.size] as? UInt64,
          size > ghosttyNavMaxLogBytes else {
        return
    }
    try? Data().write(to: URL(fileURLWithPath: ghosttyNavLogPath), options: .atomic)
}

final class NavLogger {
    private let handle: FileHandle?

    init() {
        try? ensureParentDirectory(for: ghosttyNavLogPath)
        truncateLogIfNeeded()
        if !FileManager.default.fileExists(atPath: ghosttyNavLogPath) {
            FileManager.default.createFile(atPath: ghosttyNavLogPath, contents: nil)
        }
        handle = try? FileHandle(forWritingTo: URL(fileURLWithPath: ghosttyNavLogPath))
        if let handle {
            _ = try? handle.seekToEnd()
        }
    }

    func log(_ message: String) {
        let stamp = ISO8601DateFormatter().string(from: Date())
        let line = "\(stamp) \(message)\n"
        if let data = line.data(using: .utf8) {
            handle?.write(data)
        }
    }
}
