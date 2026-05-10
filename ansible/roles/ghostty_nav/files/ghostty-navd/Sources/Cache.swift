import Foundation

let ghosttyNavCacheTTL: TimeInterval = 12 * 60 * 60

struct CacheEntry {
    let terminalID: String
    var expiresAt: Date
}

final class TerminalIDCache {
    private var entries: [String: CacheEntry] = [:]
    private let logger: NavLogger

    init(logger: NavLogger) {
        self.logger = logger
    }

    func clear(tty: String?) {
        if let tty {
            let normalized = normalizeTTY(tty)
            entries.removeValue(forKey: normalized)
            logger.log("cleared cache tty=\(normalized)")
        } else {
            entries.removeAll()
            logger.log("cleared all cache entries")
        }
    }

    func clearAfterFailure(tty: String?) {
        guard let tty else { return }
        let normalized = normalizeTTY(tty)
        entries.removeValue(forKey: normalized)
        logger.log("cleared cache tty=\(normalized) after failure")
    }

    func store(terminalID: String, for rawTTY: String) {
        let tty = normalizeTTY(rawTTY)
        entries[tty] = CacheEntry(terminalID: terminalID, expiresAt: Date().addingTimeInterval(ghosttyNavCacheTTL))
        logger.log("cached tty=\(tty) terminal_id=\(terminalID)")
    }

    func terminalID(for rawTTY: String) throws -> String {
        pruneExpired()
        let tty = normalizeTTY(rawTTY)
        if let entry = entries[tty], entry.expiresAt > Date() {
            return entry.terminalID
        }

        let terminalID = try focusedTerminalID()
        store(terminalID: terminalID, for: tty)
        return terminalID
    }

    private func pruneExpired() {
        let now = Date()
        entries = entries.filter { $0.value.expiresAt > now }
    }
}
