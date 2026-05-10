import AppKit
import Foundation

final class GhosttyNavDaemon {
    private let logger = NavLogger()
    private lazy var cache = TerminalIDCache(logger: logger)
    private let commandQueue = DispatchQueue(label: "ghostty-navd.commands")

    func start() throws -> Never {
        _ = NSApplication.shared
        logger.log("starting")
        let server = try NetworkServer(logger: logger) { [weak self] request in
            guard let self else { return .failure("daemon unavailable") }
            return commandQueue.sync { self.process(request) }
        }
        server.start()
    }

    private func process(_ request: any NavRequest) -> NavResponse {
        do {
            return try request.response(using: RequestContext(cache: cache, logger: logger))
        } catch {
            cache.clearAfterFailure(tty: request.tty)
            logger.log("\(request.logSummary) failed error=\(error.localizedDescription)")
            return .failure(error.localizedDescription)
        }
    }
}

do {
    let daemon = GhosttyNavDaemon()
    try daemon.start()
} catch {
    fputs("ghostty-navd: \(error.localizedDescription)\n", stderr)
    exit(1)
}
