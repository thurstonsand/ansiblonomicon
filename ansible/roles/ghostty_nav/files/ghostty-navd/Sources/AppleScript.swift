import AppKit
import Foundation

enum NavError: Error, LocalizedError {
    case invalidDirection(String)
    case invalidFocus(String)
    case invalidResize(String)
    case missingField(String)

    var errorDescription: String? {
        switch self {
        case let .invalidDirection(value): "invalid direction: \(value)"
        case let .invalidFocus(value): "invalid focus target: \(value)"
        case let .invalidResize(value): "invalid resize amount: \(value)"
        case let .missingField(value): "missing required field: \(value)"
        }
    }
}

enum Direction: String {
    case left
    case down
    case up
    case right
}

enum FocusTarget: String {
    case new
    case original
}

func parseDirection(_ raw: String?) throws -> Direction {
    guard let raw else { throw NavError.missingField("direction") }
    guard let direction = Direction(rawValue: raw) else { throw NavError.invalidDirection(raw) }
    return direction
}

func parseFocus(_ raw: String?) throws -> FocusTarget {
    guard let raw else { return .new }
    guard let focus = FocusTarget(rawValue: raw) else { throw NavError.invalidFocus(raw) }
    return focus
}

func executeAppleScript(_ source: String) throws -> NSAppleEventDescriptor {
    var error: NSDictionary?
    guard let script = NSAppleScript(source: source) else {
        throw NSError(
            domain: "ghostty-nav",
            code: 1,
            userInfo: [NSLocalizedDescriptionKey: "failed to compile AppleScript"]
        )
    }

    let result = script.executeAndReturnError(&error)
    if let error {
        let message = error[NSAppleScript.errorMessage] as? String ?? "AppleScript failed"
        var userInfo = error as? [String: Any] ?? [:]
        userInfo[NSLocalizedDescriptionKey] = message
        throw NSError(domain: "ghostty-nav", code: 1, userInfo: userInfo)
    }
    return result
}

func escapeAppleScriptString(_ value: String) -> String {
    value
        .replacingOccurrences(of: "\\", with: "\\\\")
        .replacingOccurrences(of: "\"", with: "\\\"")
}

func intValue(from descriptor: NSAppleEventDescriptor) throws -> Int {
    if let stringValue = descriptor.stringValue?.trimmingCharacters(in: .whitespacesAndNewlines),
       let intValue = Int(stringValue) {
        return intValue
    }

    let int32Value = Int(descriptor.int32Value)
    if int32Value != 0 || descriptor.stringValue == nil {
        return int32Value
    }

    throw NSError(
        domain: "ghostty-nav",
        code: 1,
        userInfo: [NSLocalizedDescriptionKey: "failed to decode AppleScript integer result"]
    )
}

func terminalSpecifier(id terminalID: String?) -> String {
    if let terminalID {
        return "terminal id \"\(escapeAppleScriptString(terminalID))\""
    }
    return "focused terminal of selected tab of front window"
}

func runGhosttyAction(_ action: String, terminalID: String? = nil) throws {
    let source = """
    tell application "Ghostty"
        set t to \(terminalSpecifier(id: terminalID))
        perform action "\(escapeAppleScriptString(action))" on t
    end tell
    """
    _ = try executeAppleScript(source)
}

func focusedTerminalID() throws -> String {
    let source = """
    tell application "Ghostty"
        return id of focused terminal of selected tab of front window
    end tell
    """
    let value = try executeAppleScript(source).stringValue?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    if value.isEmpty {
        throw NSError(
            domain: "ghostty-nav",
            code: 1,
            userInfo: [NSLocalizedDescriptionKey: "failed to resolve focused terminal id"]
        )
    }
    return value
}

func tabTerminalCount() throws -> Int {
    let source = """
    tell application "Ghostty"
        return count of terminals of selected tab of front window
    end tell
    """
    return try intValue(from: executeAppleScript(source))
}

func frontWindowDimension(for direction: Direction) throws -> Int {
    let axisIndex = (direction == .left || direction == .right) ? 1 : 2
    let source = """
    tell application "System Events"
        tell process "Ghostty"
            if (count of windows) is 0 then error "Ghostty has no windows"
            set winSize to size of window 1
            return item \(axisIndex) of winSize
        end tell
    end tell
    """
    return try intValue(from: executeAppleScript(source))
}

func split(direction: Direction, cwd: String?, command: String?, focus: FocusTarget, terminalID: String) throws {
    let escapedCwd = cwd.map(escapeAppleScriptString)
    let escapedCommand = command.map(escapeAppleScriptString)
    let focusTarget = focus == .original ? "targetTerminal" : "newTerminal"

    let source = """
    tell application "Ghostty"
        set targetTerminal to \(terminalSpecifier(id: terminalID))
        set cfg to new surface configuration
    \(escapedCwd.map { "    set initial working directory of cfg to \"\($0)\"" } ?? "")
    \(escapedCommand.map { "    set command of cfg to \"\($0)\"" } ?? "")
        set newTerminal to split targetTerminal direction \(direction.rawValue) with configuration cfg
        focus \(focusTarget)
    end tell
    """

    _ = try executeAppleScript(source)
}

func resize(direction: Direction, amount: ResizeAmount, terminalID: String) throws {
    let pixels: Int
    switch (amount.pixels, amount.percent) {
    case (.some(let value), nil):
        pixels = value
    case (nil, let .some(value)):
        guard value > 0 else { throw NavError.invalidResize("percent must be greater than 0") }
        let dimension = try frontWindowDimension(for: direction)
        pixels = max(Int(Double(dimension) * value / 100.0), 1)
    default:
        throw NavError.invalidResize("specify exactly one of pixels or percent")
    }

    guard pixels > 0 else { throw NavError.invalidResize("pixels must be greater than 0") }
    try runGhosttyAction("resize_split:\(direction.rawValue),\(pixels)", terminalID: terminalID)
}
