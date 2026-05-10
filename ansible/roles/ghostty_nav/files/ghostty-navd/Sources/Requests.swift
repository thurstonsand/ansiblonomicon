import Foundation

protocol NavRequest: Decodable {
    var command: String { get }
    var reply: Bool { get }
    var tty: String? { get }
    func response(using context: RequestContext) throws -> NavResponseBody
}

extension NavRequest {
    var logSummary: String {
        var parts = ["command=\(command)"]
        if let tty { parts.append("tty=\(tty)") }
        return parts.joined(separator: " ")
    }
}

struct RequestContext {
    let cache: TerminalIDCache
    let logger: NavLogger
}

struct Envelope: Decodable {
    let command: String
    let reply: Bool
}

struct ResizeAmount: Decodable {
    let pixels: Int?
    let percent: Double?
}

struct PingRequest: NavRequest {
    let command: String
    let reply: Bool

    var tty: String? {
        nil
    }

    func response(using _: RequestContext) throws -> NavResponseBody {
        .json(NavResponse.ok("pong"))
    }
}

struct TerminalIDRequest: NavRequest {
    let command: String
    let reply: Bool
    let rawTTY: String?

    enum CodingKeys: String, CodingKey {
        case command
        case reply
        case rawTTY = "tty"
    }

    var tty: String? {
        rawTTY.map(normalizeTTY)
    }

    func response(using context: RequestContext) throws -> NavResponseBody {
        let id = try focusedTerminalID()
        if let tty {
            context.cache.store(terminalID: id, for: tty)
        }
        return .json(NavResponse.ok(id))
    }
}

struct TabTerminalCountRequest: NavRequest {
    let command: String
    let reply: Bool

    var tty: String? {
        nil
    }

    func response(using _: RequestContext) throws -> NavResponseBody {
        let count = try tabTerminalCount()
        return .json(NavResponse.ok(String(count)))
    }
}

struct ClearCacheRequest: NavRequest {
    let command: String
    let reply: Bool
    let rawTTY: String?

    enum CodingKeys: String, CodingKey {
        case command
        case reply
        case rawTTY = "tty"
    }

    var tty: String? {
        rawTTY.map(normalizeTTY)
    }

    var logSummary: String {
        if tty == nil { return "command=\(command) scope=all" }
        return "command=\(command) tty=\(tty ?? "")"
    }

    func response(using context: RequestContext) throws -> NavResponseBody {
        context.cache.clear(tty: tty)
        return .json(NavResponse.ok())
    }
}

struct ActivateRequest: NavRequest {
    let command: String
    let reply: Bool
    let rawTTY: String
    let table: String

    enum CodingKeys: String, CodingKey {
        case command
        case reply
        case rawTTY = "tty"
        case table
    }

    var tty: String? {
        normalizeTTY(rawTTY)
    }

    var logSummary: String {
        "command=\(command) tty=\(tty ?? "") table=\(table)"
    }

    func response(using context: RequestContext) throws -> NavResponseBody {
        let terminalID = try context.cache.terminalID(for: normalizeTTY(rawTTY))
        try runGhosttyAction("activate_key_table:\(table)", terminalID: terminalID)
        return .json(NavResponse.ok())
    }
}

struct DeactivateRequest: NavRequest {
    let command: String
    let reply: Bool
    let rawTTY: String

    enum CodingKeys: String, CodingKey {
        case command
        case reply
        case rawTTY = "tty"
    }

    var tty: String? {
        normalizeTTY(rawTTY)
    }

    func response(using context: RequestContext) throws -> NavResponseBody {
        let terminalID = try context.cache.terminalID(for: normalizeTTY(rawTTY))
        try runGhosttyAction("deactivate_key_table", terminalID: terminalID)
        return .json(NavResponse.ok())
    }
}

struct MoveRequest: NavRequest {
    let command: String
    let reply: Bool
    let rawTTY: String
    let direction: String

    enum CodingKeys: String, CodingKey {
        case command
        case reply
        case rawTTY = "tty"
        case direction
    }

    var tty: String? {
        normalizeTTY(rawTTY)
    }

    var logSummary: String {
        "command=\(command) tty=\(tty ?? "") direction=\(direction)"
    }

    func response(using context: RequestContext) throws -> NavResponseBody {
        let terminalID = try context.cache.terminalID(for: normalizeTTY(rawTTY))
        let parsedDirection = try parseDirection(direction)
        try runGhosttyAction("goto_split:\(parsedDirection.rawValue)", terminalID: terminalID)
        return .json(NavResponse.ok())
    }
}

struct SplitRequest: NavRequest {
    let command: String
    let reply: Bool
    let rawTTY: String
    let direction: String
    let cwd: String?
    let commandText: String?
    let focus: String?

    enum CodingKeys: String, CodingKey {
        case command
        case reply
        case rawTTY = "tty"
        case direction
        case cwd
        case commandText
        case focus
    }

    var tty: String? {
        normalizeTTY(rawTTY)
    }

    var logSummary: String {
        "command=\(command) tty=\(tty ?? "") direction=\(direction)"
    }

    func response(using context: RequestContext) throws -> NavResponseBody {
        let terminalID = try context.cache.terminalID(for: normalizeTTY(rawTTY))
        let parsedDirection = try parseDirection(direction)
        let parsedFocus = try parseFocus(focus)
        try split(
            direction: parsedDirection,
            cwd: cwd,
            command: commandText,
            focus: parsedFocus,
            terminalID: terminalID
        )
        return .json(NavResponse.ok())
    }
}

struct ResizeCommandRequest: NavRequest {
    let command: String
    let reply: Bool
    let rawTTY: String
    let direction: String
    let amount: ResizeAmount

    enum CodingKeys: String, CodingKey {
        case command
        case reply
        case rawTTY = "tty"
        case direction
        case amount
    }

    var tty: String? {
        normalizeTTY(rawTTY)
    }

    var logSummary: String {
        "command=\(command) tty=\(tty ?? "") direction=\(direction)"
    }

    func response(using context: RequestContext) throws -> NavResponseBody {
        let terminalID = try context.cache.terminalID(for: normalizeTTY(rawTTY))
        let parsedDirection = try parseDirection(direction)
        try resize(direction: parsedDirection, amount: amount, terminalID: terminalID)
        return .json(NavResponse.ok())
    }
}

struct ToggleZoomRequest: NavRequest {
    let command: String
    let reply: Bool
    let rawTTY: String

    enum CodingKeys: String, CodingKey {
        case command
        case reply
        case rawTTY = "tty"
    }

    var tty: String? {
        normalizeTTY(rawTTY)
    }

    func response(using context: RequestContext) throws -> NavResponseBody {
        let terminalID = try context.cache.terminalID(for: normalizeTTY(rawTTY))
        try runGhosttyAction("toggle_split_zoom", terminalID: terminalID)
        return .json(NavResponse.ok())
    }
}

struct PasteRequest: NavRequest {
    let command: String
    let reply: Bool
    let rawTTY: String?

    enum CodingKeys: String, CodingKey {
        case command
        case reply
        case rawTTY = "tty"
    }

    var tty: String? {
        rawTTY.map(normalizeTTY)
    }

    func response(using _: RequestContext) throws -> NavResponseBody {
        try .stream(readPasteboardContent())
    }
}

enum NavResponseBody {
    case json(any Encodable)
    case stream(PasteStreamResponse)
}

struct NavResponse: Encodable {
    let value: String?
    let error: String?

    static func ok(_ value: String? = nil) -> NavResponse {
        NavResponse(value: value, error: nil)
    }

    static func failure(_ error: String) -> NavResponse {
        NavResponse(value: nil, error: error)
    }
}

struct PasteFileResponse: Encodable {
    let fileName: String?
    let mediaType: String?
    let bytes: Int
    let source: String?
}

struct PasteResponse: Encodable {
    let value: String?
    let error: String?
    let kind: String?
    let text: String?
    let files: [PasteFileResponse]?
    let bytes: Int?

    static func text(_ text: String) -> PasteResponse {
        PasteResponse(
            value: nil,
            error: nil,
            kind: "text",
            text: text,
            files: nil,
            bytes: nil
        )
    }

    static func files(_ files: [PasteFileResponse]) -> PasteResponse {
        PasteResponse(
            value: nil,
            error: nil,
            kind: "files",
            text: nil,
            files: files,
            bytes: files.reduce(0) { $0 + $1.bytes }
        )
    }
}

enum PasteByteStream {
    case data(Data)
    case file(URL)
}

struct PasteStreamResponse {
    let header: PasteResponse
    let streams: [PasteByteStream]
}

func normalizeTTY(_ tty: String) -> String {
    tty.hasPrefix("/dev/") ? tty : "/dev/\(tty)"
}

func encodeJSONLine(_ value: any Encodable) throws -> Data {
    var data = try JSONEncoder().encode(value)
    data.append(0x0A)
    return data
}

func decodeNavRequest(from data: Data) throws -> any NavRequest {
    let trimmed = linePayload(from: data)
    let envelope = try JSONDecoder().decode(Envelope.self, from: trimmed)
    guard let decode = requestDecoders[envelope.command] else {
        throw NSError(
            domain: "ghostty-navd",
            code: 1,
            userInfo: [NSLocalizedDescriptionKey: "unsupported command: \(envelope.command)"]
        )
    }
    return try decode(trimmed)
}

private let requestDecoders: [String: (Data) throws -> any NavRequest] = [
    "ping": { try JSONDecoder().decode(PingRequest.self, from: $0) },
    "terminal-id": { try JSONDecoder().decode(TerminalIDRequest.self, from: $0) },
    "tab-terminal-count": { try JSONDecoder().decode(TabTerminalCountRequest.self, from: $0) },
    "clear-cache": { try JSONDecoder().decode(ClearCacheRequest.self, from: $0) },
    "activate": { try JSONDecoder().decode(ActivateRequest.self, from: $0) },
    "deactivate": { try JSONDecoder().decode(DeactivateRequest.self, from: $0) },
    "move": { try JSONDecoder().decode(MoveRequest.self, from: $0) },
    "split": { try JSONDecoder().decode(SplitRequest.self, from: $0) },
    "resize": { try JSONDecoder().decode(ResizeCommandRequest.self, from: $0) },
    "toggle-zoom": { try JSONDecoder().decode(ToggleZoomRequest.self, from: $0) },
    "paste": { try JSONDecoder().decode(PasteRequest.self, from: $0) }
]

private func linePayload(from data: Data) -> Data {
    if let newline = data.firstIndex(of: 0x0A) {
        return Data(data[..<newline])
    }
    return data
}
