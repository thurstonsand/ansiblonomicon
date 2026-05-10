import Foundation
import Network

let ghosttyNavSocketPath = FileManager.default.homeDirectoryForCurrentUser
    .appendingPathComponent(".local/run/ghostty-nav/ghostty-navd.sock")
    .path

final class NetworkServer {
    private let listener: NWListener
    private let queue = DispatchQueue(label: "ghostty-navd.network")
    private let logger: NavLogger
    private let handler: (any NavRequest) -> NavResponseBody
    private var connections: [UUID: ClientConnection] = [:]

    init(logger: NavLogger, handler: @escaping (any NavRequest) -> NavResponseBody) throws {
        self.logger = logger
        self.handler = handler

        try ensureParentDirectory(for: ghosttyNavSocketPath)
        try? FileManager.default.removeItem(atPath: ghosttyNavSocketPath)

        let params = NWParameters()
        params.defaultProtocolStack.transportProtocol = NWProtocolTCP.Options()
        params.requiredLocalEndpoint = NWEndpoint.unix(path: ghosttyNavSocketPath)
        params.allowLocalEndpointReuse = true
        listener = try NWListener(using: params)
    }

    func start() -> Never {
        listener.stateUpdateHandler = { [logger] state in
            switch state {
            case .ready:
                logger.log("listening socket=\(ghosttyNavSocketPath)")
            case let .failed(error):
                logger.log("listener failed error=\(error)")
                exit(1)
            case .cancelled:
                logger.log("listener cancelled")
            default:
                break
            }
        }

        listener.newConnectionHandler = { [weak self] connection in
            self?.accept(connection)
        }

        listener.start(queue: queue)
        dispatchMain()
    }

    private func accept(_ connection: NWConnection) {
        let id = UUID()
        let client = ClientConnection(id: id, connection: connection, queue: queue, logger: logger, handler: handler)
        client.didStop = { [weak self] connectionID in
            self?.connections.removeValue(forKey: connectionID)
        }
        connections[id] = client
        client.start()
    }
}

private final class ClientConnection {
    let id: UUID
    var didStop: ((UUID) -> Void)?

    private let connection: NWConnection
    private let queue: DispatchQueue
    private let logger: NavLogger
    private let handler: (any NavRequest) -> NavResponseBody
    private var buffer = Data()
    private var stopped = false

    init(
        id: UUID,
        connection: NWConnection,
        queue: DispatchQueue,
        logger: NavLogger,
        handler: @escaping (any NavRequest) -> NavResponseBody
    ) {
        self.id = id
        self.connection = connection
        self.queue = queue
        self.logger = logger
        self.handler = handler
    }

    func start() {
        connection.stateUpdateHandler = { [weak self] state in
            self?.stateDidChange(to: state)
        }
        receiveNextChunk()
        connection.start(queue: queue)
    }

    private func stateDidChange(to state: NWConnection.State) {
        guard !stopped else { return }
        if case let .failed(error) = state {
            logger.log("connection failed error=\(error)")
            stop()
        }
    }

    private func receiveNextChunk() {
        connection.receive(minimumIncompleteLength: 1, maximumLength: 4096) { [weak self] data, _, isComplete, error in
            guard let self else { return }
            if let data, !data.isEmpty {
                buffer.append(data)
            }

            if let requestLine = nextRequestLine() {
                handle(data: requestLine)
                return
            }

            if !buffer.isEmpty, isComplete || error != nil {
                handle(data: buffer)
                return
            }

            if let error {
                logger.log("receive failed error=\(error)")
                stop()
                return
            }

            if isComplete {
                logger.log("empty request")
                stop()
                return
            }

            receiveNextChunk()
        }
    }

    private func nextRequestLine() -> Data? {
        guard let newline = buffer.firstIndex(of: 0x0A) else { return nil }
        let requestLine = Data(buffer[..<newline])
        buffer.removeAll(keepingCapacity: true)
        return requestLine
    }

    private func handle(data: Data) {
        let response: NavResponseBody
        let wantsReply: Bool
        do {
            let request = try decodeNavRequest(from: data)
            wantsReply = request.reply
            response = handler(request)
        } catch {
            wantsReply = true
            logger.log("request failed before process error=\(error.localizedDescription)")
            response = .json(NavResponse.failure(error.localizedDescription))
        }

        if wantsReply {
            send(response)
        } else {
            stop()
        }
    }

    private func send(_ response: NavResponseBody) {
        switch response {
        case let .json(jsonResponse):
            sendJSON(jsonResponse, isComplete: true) { [weak self] in self?.stop() }
        case let .stream(streamResponse):
            send(streamResponse)
        }
    }

    private func send(_ response: PasteStreamResponse) {
        sendJSON(response.header, isComplete: response.streams.isEmpty) { [weak self] in
            guard let self else { return }
            if response.streams.isEmpty {
                stop()
                return
            }
            sendStreams(response.streams, index: 0)
        }
    }

    private func sendJSON(_ response: any Encodable, isComplete: Bool, complete: @escaping () -> Void) {
        do {
            let responseData = try encodeJSONLine(response)
            connection.send(
                content: responseData,
                contentContext: .defaultMessage,
                isComplete: isComplete,
                completion: .contentProcessed { [weak self] error in
                    if let error {
                        self?.logger.log("send failed error=\(error)")
                        self?.stop()
                        return
                    }
                    complete()
                }
            )
        } catch {
            logger.log("response encode failed error=\(error.localizedDescription)")
            stop()
        }
    }

    private func sendStreams(_ streams: [PasteByteStream], index: Int) {
        if index >= streams.count {
            connection.send(
                content: nil,
                contentContext: .finalMessage,
                isComplete: true,
                completion: .contentProcessed { [weak self] _ in
                    self?.stop()
                }
            )
            return
        }

        switch streams[index] {
        case let .data(data):
            sendData(data) { [weak self] in self?.sendStreams(streams, index: index + 1) }
        case let .file(url):
            sendFile(url) { [weak self] in self?.sendStreams(streams, index: index + 1) }
        }
    }

    private func sendData(_ data: Data, complete: @escaping () -> Void) {
        connection.send(
            content: data,
            contentContext: .defaultMessage,
            isComplete: false,
            completion: .contentProcessed { [weak self] error in
                if let error {
                    self?.logger.log("stream data send failed error=\(error)")
                    self?.stop()
                    return
                }
                complete()
            }
        )
    }

    private func sendFile(_ url: URL, complete: @escaping () -> Void) {
        do {
            let handle = try FileHandle(forReadingFrom: url)
            sendFileChunk(handle, complete: complete)
        } catch {
            logger.log("stream file open failed error=\(error.localizedDescription)")
            stop()
        }
    }

    private func sendFileChunk(_ handle: FileHandle, complete: @escaping () -> Void) {
        do {
            guard let chunk = try handle.read(upToCount: 1024 * 1024), !chunk.isEmpty else {
                try? handle.close()
                complete()
                return
            }
            connection.send(
                content: chunk,
                contentContext: .defaultMessage,
                isComplete: false,
                completion: .contentProcessed { [weak self] error in
                    if let error {
                        self?.logger.log("stream file send failed error=\(error)")
                        try? handle.close()
                        self?.stop()
                        return
                    }
                    self?.sendFileChunk(handle, complete: complete)
                }
            )
        } catch {
            logger.log("stream file read failed error=\(error.localizedDescription)")
            try? handle.close()
            stop()
        }
    }

    private func stop() {
        guard !stopped else { return }
        stopped = true
        connection.stateUpdateHandler = nil
        connection.cancel()
        didStop?(id)
        didStop = nil
    }
}

func ensureParentDirectory(for path: String) throws {
    let parent = URL(fileURLWithPath: path).deletingLastPathComponent()
    try FileManager.default.createDirectory(
        at: parent,
        withIntermediateDirectories: true,
        attributes: [.posixPermissions: 0o700]
    )
}
