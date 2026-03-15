import AppKit

// Four-char codes from Ghostty's scripting dictionary (sdef).
// Suite code: Ghst

// MARK: - FourCharCode helpers

func fourCC(_ s: String) -> FourCharCode {
    var result: FourCharCode = 0
    for byte in s.utf8.prefix(4) {
        result = (result << 8) | FourCharCode(byte)
    }
    return result
}

let kGhosttyBundleID = "com.mitchellh.ghostty"

// Class codes
let cWindow = fourCC("Gwnd")
let cTab = fourCC("Gtab")
let cTerminal = fourCC("Gtrm")

// Property codes
let pFrontWindow = fourCC("GFWn")
let pSelectedTab = fourCC("GWsT")
let pFocusedTerminal = fourCC("GTfT")
let pName = fourCC("pnam")

// Command codes
let kPerformAction = AEEventID(fourCC("PfAc"))
let kGhosttyEventClass = AEEventClass(fourCC("Ghst"))

// Parameter codes
let pOnTerminal = fourCC("GonT")

// MARK: - Direction

enum Direction: String {
    case left, down, up, right
}

// MARK: - Apple Event helpers

func ghosttyAddress() -> NSAppleEventDescriptor {
    NSAppleEventDescriptor(bundleIdentifier: kGhosttyBundleID)
}

/// Build the object specifier chain: focused terminal of selected tab of front window
func focusedTerminalSpecifier() -> NSAppleEventDescriptor {
    let frontWindow = NSAppleEventDescriptor(
        descriptorType: typeObjectSpecifier,
        data: packObjectSpecifier(
            wantClass: cWindow,
            container: NSAppleEventDescriptor.null(),
            keyForm: FourCharCode(formPropertyID),
            keyData: NSAppleEventDescriptor(typeCode: pFrontWindow)
        )
    )!

    let selectedTab = NSAppleEventDescriptor(
        descriptorType: typeObjectSpecifier,
        data: packObjectSpecifier(
            wantClass: cTab,
            container: frontWindow,
            keyForm: FourCharCode(formPropertyID),
            keyData: NSAppleEventDescriptor(typeCode: pSelectedTab)
        )
    )!

    return NSAppleEventDescriptor(
        descriptorType: typeObjectSpecifier,
        data: packObjectSpecifier(
            wantClass: cTerminal,
            container: selectedTab,
            keyForm: FourCharCode(formPropertyID),
            keyData: NSAppleEventDescriptor(typeCode: pFocusedTerminal)
        )
    )!
}

func packObjectSpecifier(
    wantClass: FourCharCode,
    container: NSAppleEventDescriptor,
    keyForm: FourCharCode,
    keyData: NSAppleEventDescriptor
) -> Data? {
    let record = NSAppleEventDescriptor.record()
    record.setDescriptor(NSAppleEventDescriptor(typeCode: wantClass), forKeyword: AEKeyword(keyAEDesiredClass))
    record.setDescriptor(container, forKeyword: AEKeyword(keyAEContainer))
    record.setDescriptor(NSAppleEventDescriptor(enumCode: keyForm), forKeyword: AEKeyword(keyAEKeyForm))
    record.setDescriptor(keyData, forKeyword: AEKeyword(keyAEKeyData))
    return record.coerce(toDescriptorType: typeObjectSpecifier)?.data
}

func sendEvent(_ event: NSAppleEventDescriptor) -> NSAppleEventDescriptor? {
    let reply: NSAppleEventDescriptor
    do {
        reply = try event.sendEvent(
            options: [.waitForReply],
            timeout: TimeInterval(5)
        )
    } catch {
        fputs("error: \(error.localizedDescription)\n", stderr)
        exit(1)
    }
    if let errorNum = reply.paramDescriptor(forKeyword: AEKeyword(keyErrorNumber)),
       errorNum.int32Value != 0
    {
        let errorMsg =
            reply.paramDescriptor(forKeyword: AEKeyword(keyErrorString))?.stringValue
                ?? "unknown error"
        fputs("error: \(errorMsg) (\(errorNum.int32Value))\n", stderr)
        exit(1)
    }
    return reply
}

// MARK: - Terminal name query

func getTerminalName() -> String {
    let terminal = focusedTerminalSpecifier()

    // Build a "get name of <terminal>" event
    let nameSpec = NSAppleEventDescriptor(
        descriptorType: typeObjectSpecifier,
        data: packObjectSpecifier(
            wantClass: fourCC("prop"),
            container: terminal,
            keyForm: FourCharCode(formPropertyID),
            keyData: NSAppleEventDescriptor(typeCode: pName)
        )
    )!

    let event = NSAppleEventDescriptor.appleEvent(
        withEventClass: AEEventClass(kAECoreSuite),
        eventID: AEEventID(kAEGetData),
        targetDescriptor: ghosttyAddress(),
        returnID: AEReturnID(kAutoGenerateReturnID),
        transactionID: AETransactionID(kAnyTransactionID)
    )
    event.setParam(nameSpec, forKeyword: keyDirectObject)

    guard let reply = sendEvent(event),
        let result = reply.paramDescriptor(forKeyword: keyDirectObject)?.stringValue
    else {
        return ""
    }
    return result
}

// MARK: - Navigation commands

func performAction(_ action: String, on terminal: NSAppleEventDescriptor) {
    let event = NSAppleEventDescriptor.appleEvent(
        withEventClass: kGhosttyEventClass,
        eventID: kPerformAction,
        targetDescriptor: ghosttyAddress(),
        returnID: AEReturnID(kAutoGenerateReturnID),
        transactionID: AETransactionID(kAnyTransactionID)
    )
    event.setParam(NSAppleEventDescriptor(string: action), forKeyword: keyDirectObject)
    event.setParam(terminal, forKeyword: pOnTerminal)
    _ = sendEvent(event)
}

func sendKeystroke(_ dir: Direction) {
    let keys: [Direction: String] = [.left: "h", .down: "j", .up: "k", .right: "l"]
    let sysEventsAddr = NSAppleEventDescriptor(bundleIdentifier: "com.apple.systemevents")
    let event = NSAppleEventDescriptor.appleEvent(
        withEventClass: AEEventClass(fourCC("prcs")),
        eventID: AEEventID(fourCC("kprs")),
        targetDescriptor: sysEventsAddr,
        returnID: AEReturnID(kAutoGenerateReturnID),
        transactionID: AETransactionID(kAnyTransactionID)
    )
    event.setParam(NSAppleEventDescriptor(string: keys[dir]!), forKeyword: keyDirectObject)
    event.setParam(NSAppleEventDescriptor(enumCode: fourCC("Kctl")), forKeyword: fourCC("faal"))
    _ = try? event.sendEvent(options: [.waitForReply], timeout: 5)
}

func gotoSplit(_ dir: Direction) {
    performAction("goto_split:\(dir.rawValue)", on: focusedTerminalSpecifier())
}

func navigate(_ dir: Direction) {
    let terminal = focusedTerminalSpecifier()
    let name = getTerminalName()

    // U+200B (zero-width space) is prepended to Neovim's titlestring.
    // Invisible in the tab/title bar but detectable here.
    if name.hasPrefix("\u{200B}") {
        sendKeystroke(dir)
    } else {
        performAction("goto_split:\(dir.rawValue)", on: terminal)
    }
}

// MARK: - Main

var args = Array(CommandLine.arguments.dropFirst())

var ghosttyOnly = false
if args.first == "--ghostty-only" {
    ghosttyOnly = true
    args.removeFirst()
}

guard let rawDir = args.first, let dir = Direction(rawValue: rawDir), args.count == 1 else {
    fputs("usage: ghostty-nav [--ghostty-only] left|down|up|right\n", stderr)
    exit(1)
}

if ghosttyOnly {
    gotoSplit(dir)
} else {
    navigate(dir)
}
