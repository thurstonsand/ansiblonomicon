import Foundation
import Network

let ghosttyNavSocketPath = FileManager.default.homeDirectoryForCurrentUser
    .appendingPathComponent(".local/run/ghostty-nav/ghostty-navd.sock")
    .path

final class NetworkServer {
    private let listener: NWListener
    private let queue = DispatchQueue(label: "ghostty-navd.network")
    private let logger: NavLogger
    private let handler: (any NavRequest) -> NavResponse
    private var connections: [UUID: ClientConnection] = [:]

    init(logger: NavLogger, handler: @escaping (any NavRequest) -> NavResponse) throws {
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
    private let handler: (any NavRequest) -> NavResponse
    private var buffer = Data()
    private var stopped = false

    init(
        id: UUID,
        connection: NWConnection,
        queue: DispatchQueue,
        logger: NavLogger,
        handler: @escaping (any NavRequest) -> NavResponse
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
        let response: NavResponse
        let wantsReply: Bool
        do {
            let request = try decodeNavRequest(from: data)
            wantsReply = request.reply
            response = handler(request)
        } catch {
            wantsReply = true
            logger.log("request failed before process error=\(error.localizedDescription)")
            response = .failure(error.localizedDescription)
        }

        if wantsReply {
            send(response)
        } else {
            stop()
        }
    }

    private func send(_ response: NavResponse) {
        do {
            let responseData = try encodeJSONLine(response)
            connection.send(
                content: responseData,
                contentContext: .finalMessage,
                isComplete: true,
                completion: .contentProcessed { [weak self] error in
                    if let error {
                        self?.logger.log("send failed error=\(error)")
                    }
                    self?.stop()
                }
            )
        } catch {
            logger.log("response encode failed error=\(error.localizedDescription)")
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
