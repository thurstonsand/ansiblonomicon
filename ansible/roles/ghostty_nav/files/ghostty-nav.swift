import Foundation
import AppKit

func usage() -> Never {
    fputs(
        "usage: ghostty-nav activate <table> | deactivate | move <left|down|up|right> | tab-terminal-count | split <left|right|up|down> [--cwd <path>] [--command <string>] [--focus <new|original>] | resize <left|down|up|right> (--pixels <n> | --percent <n>) | toggle-zoom | title <text>\n",
        stderr
    )
    exit(2)
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

enum ResizeAmount {
    case pixels(Int)
    case percent(Double)
}

enum Command {
    case activate(String)
    case deactivate
    case move(Direction)
    case tabTerminalCount
    case split(Direction, cwd: String?, command: String?, focus: FocusTarget)
    case resize(Direction, amount: ResizeAmount)
    case toggleZoom
    case title(String)
}

func parseDirection(_ rawValue: String) -> Direction {
    guard let direction = Direction(rawValue: rawValue) else { usage() }
    return direction
}

func parseFocusTarget(_ rawValue: String) -> FocusTarget {
    guard let target = FocusTarget(rawValue: rawValue) else { usage() }
    return target
}

func parseInt(_ rawValue: String) -> Int {
    guard let value = Int(rawValue) else { usage() }
    return value
}

func parseDouble(_ rawValue: String) -> Double {
    guard let value = Double(rawValue) else { usage() }
    return value
}

func parseCommand(_ args: [String]) -> Command {
    guard args.count >= 2 else { usage() }

    switch args[1] {
    case "activate":
        guard args.count == 3 else { usage() }
        return .activate(args[2])
    case "deactivate":
        guard args.count == 2 else { usage() }
        return .deactivate
    case "move":
        guard args.count == 3 else { usage() }
        return .move(parseDirection(args[2]))
    case "tab-terminal-count":
        guard args.count == 2 else { usage() }
        return .tabTerminalCount
    case "split":
        guard args.count >= 3 else { usage() }
        let direction = parseDirection(args[2])
        var cwd: String?
        var command: String?
        var focus: FocusTarget = .new

        var index = 3
        while index < args.count {
            switch args[index] {
            case "--cwd":
                guard index + 1 < args.count else { usage() }
                cwd = args[index + 1]
                index += 2
            case "--command":
                guard index + 1 < args.count else { usage() }
                command = args[index + 1]
                index += 2
            case "--focus":
                guard index + 1 < args.count else { usage() }
                focus = parseFocusTarget(args[index + 1])
                index += 2
            default:
                usage()
            }
        }

        return .split(direction, cwd: cwd, command: command, focus: focus)
    case "resize":
        guard args.count >= 5 else { usage() }
        let direction = parseDirection(args[2])
        var amount: ResizeAmount?

        var index = 3
        while index < args.count {
            switch args[index] {
            case "--pixels":
                guard index + 1 < args.count, amount == nil else { usage() }
                amount = .pixels(parseInt(args[index + 1]))
                index += 2
            case "--percent":
                guard index + 1 < args.count, amount == nil else { usage() }
                amount = .percent(parseDouble(args[index + 1]))
                index += 2
            default:
                usage()
            }
        }

        guard let amount else { usage() }
        return .resize(direction, amount: amount)
    case "toggle-zoom":
        guard args.count == 2 else { usage() }
        return .toggleZoom
    case "title":
        guard args.count == 3 else { usage() }
        return .title(args[2])
    default:
        usage()
    }
}

func sanitizeTitle(_ value: String) -> String {
    let scalars = value.unicodeScalars.filter { !CharacterSet.controlCharacters.contains($0) }
    return String(String.UnicodeScalarView(scalars))
}

func emitTitle(_ value: String) throws {
    let title = sanitizeTitle(value)
    let data = Data("\u{1B}]2;\(title)\u{07}".utf8)

    if let tty = try? FileHandle(forWritingTo: URL(fileURLWithPath: "/dev/tty")) {
        defer { try? tty.close() }
        tty.write(data)
        return
    }

    FileHandle.standardOutput.write(data)
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
        throw NSError(domain: "ghostty-nav", code: 1, userInfo: error as? [String: Any])
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

func runGhosttyAction(_ action: String) throws {
    let escapedAction = escapeAppleScriptString(action)
    let source = """
    tell application "Ghostty"
        set t to focused terminal of selected tab of front window
        perform action "\(escapedAction)" on t
    end tell
    """
    _ = try executeAppleScript(source)
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

func split(direction: Direction, cwd: String?, command: String?, focus: FocusTarget) throws {
    let escapedCwd = cwd.map(escapeAppleScriptString)
    let escapedCommand = command.map(escapeAppleScriptString)
    let focusTarget = focus.rawValue == FocusTarget.original.rawValue ? "targetTerminal" : "newTerminal"

    let source = """
    tell application "Ghostty"
        set targetTerminal to focused terminal of selected tab of front window
        set cfg to new surface configuration
    \(escapedCwd.map { "    set initial working directory of cfg to \"\($0)\"" } ?? "")
    \(escapedCommand.map { "    set command of cfg to \"\($0)\"" } ?? "")
        set newTerminal to split targetTerminal direction \(direction.rawValue) with configuration cfg
        focus \(focusTarget)
    end tell
    """

    _ = try executeAppleScript(source)
}

func resize(direction: Direction, amount: ResizeAmount) throws {
    let pixels: Int
    switch amount {
    case .pixels(let value):
        pixels = value
    case .percent(let value):
        guard value > 0 else {
            throw NSError(
                domain: "ghostty-nav",
                code: 1,
                userInfo: [NSLocalizedDescriptionKey: "resize percent must be greater than 0"]
            )
        }
        let dimension = try frontWindowDimension(for: direction)
        pixels = max(Int(Double(dimension) * value / 100.0), 1)
    }

    guard pixels > 0 else {
        throw NSError(
            domain: "ghostty-nav",
            code: 1,
            userInfo: [NSLocalizedDescriptionKey: "resize pixels must be greater than 0"]
        )
    }

    try runGhosttyAction("resize_split:\(direction.rawValue),\(pixels)")
}

let command = parseCommand(CommandLine.arguments)

do {
    switch command {
    case .activate(let table):
        try runGhosttyAction("activate_key_table:\(table)")
    case .deactivate:
        try runGhosttyAction("deactivate_key_table")
    case .move(let direction):
        try runGhosttyAction("goto_split:\(direction.rawValue)")
    case .tabTerminalCount:
        print(try tabTerminalCount())
    case .split(let direction, let cwd, let command, let focus):
        try split(direction: direction, cwd: cwd, command: command, focus: focus)
    case .resize(let direction, let amount):
        try resize(direction: direction, amount: amount)
    case .toggleZoom:
        try runGhosttyAction("toggle_split_zoom")
    case .title(let value):
        try emitTitle(value)
    }
} catch {
    fputs("ghostty-nav: \(error.localizedDescription)\n", stderr)
    exit(1)
}
