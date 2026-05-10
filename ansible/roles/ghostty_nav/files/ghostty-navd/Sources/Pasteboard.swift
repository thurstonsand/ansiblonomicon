import AppKit
import Foundation
import UniformTypeIdentifiers

func readPasteboardContent() throws -> PasteStreamResponse {
    let pasteboard = NSPasteboard.general

    let fileItems = try readFileURLItems(from: pasteboard)
    if !fileItems.isEmpty {
        return pasteStreamResponse(fileItems)
    }

    if let imageItem = readImageItem(from: pasteboard) {
        return pasteStreamResponse([imageItem])
    }

    if let dataItem = readTypedDataItem(from: pasteboard) {
        return pasteStreamResponse([dataItem])
    }

    if let text = pasteboard.string(forType: .string), !text.isEmpty {
        return PasteStreamResponse(header: .text(text), streams: [])
    }

    throw NSError(
        domain: "ghostty-navd",
        code: 2,
        userInfo: [NSLocalizedDescriptionKey: "clipboard has no supported content"]
    )
}

private struct PasteboardFileItem {
    let response: PasteFileResponse
    let stream: PasteByteStream
}

private func pasteStreamResponse(_ items: [PasteboardFileItem]) -> PasteStreamResponse {
    PasteStreamResponse(header: .files(items.map(\.response)), streams: items.map(\.stream))
}

private func readFileURLItems(from pasteboard: NSPasteboard) throws -> [PasteboardFileItem] {
    let objects = pasteboard.readObjects(
        forClasses: [NSURL.self],
        options: [.urlReadingFileURLsOnly: true]
    ) ?? []
    let urls = objects.compactMap { object -> URL? in
        if let url = object as? URL { return url }
        if let url = object as? NSURL { return url as URL }
        return nil
    }

    return try urls.filter { !$0.hasDirectoryPath }.map { url in
        let bytes = try fileSize(url)
        return PasteboardFileItem(
            response: PasteFileResponse(
                fileName: url.lastPathComponent,
                mediaType: mediaType(forFileExtension: url.pathExtension),
                bytes: bytes,
                source: "pasteboard-file"
            ),
            stream: .file(url)
        )
    }
}

private func readImageItem(from pasteboard: NSPasteboard) -> PasteboardFileItem? {
    let data: Data
    if let pngData = pasteboard.data(forType: .png), !pngData.isEmpty {
        data = pngData
    } else if let tiffData = pasteboard.data(forType: .tiff), !tiffData.isEmpty,
              let converted = pngData(fromImageData: tiffData) {
        data = converted
    } else if let image = NSImage(pasteboard: pasteboard), let converted = pngData(from: image) {
        data = converted
    } else {
        return nil
    }

    return PasteboardFileItem(
        response: PasteFileResponse(
            fileName: "clipboard.png",
            mediaType: "image/png",
            bytes: data.count,
            source: "pasteboard-image"
        ),
        stream: .data(data)
    )
}

private struct PasteboardDataCandidate {
    let type: NSPasteboard.PasteboardType
    let fileName: String
    let mediaType: String
}

private func readTypedDataItem(from pasteboard: NSPasteboard) -> PasteboardFileItem? {
    let candidates = [
        PasteboardDataCandidate(type: .pdf, fileName: "clipboard.pdf", mediaType: "application/pdf"),
        PasteboardDataCandidate(type: .rtf, fileName: "clipboard.rtf", mediaType: "application/rtf"),
        PasteboardDataCandidate(type: .html, fileName: "clipboard.html", mediaType: "text/html")
    ]

    for candidate in candidates {
        if let data = pasteboard.data(forType: candidate.type), !data.isEmpty {
            return PasteboardFileItem(
                response: PasteFileResponse(
                    fileName: candidate.fileName,
                    mediaType: candidate.mediaType,
                    bytes: data.count,
                    source: "pasteboard-data"
                ),
                stream: .data(data)
            )
        }
    }
    return nil
}

private func fileSize(_ url: URL) throws -> Int {
    let values = try url.resourceValues(forKeys: [.fileSizeKey])
    if let size = values.fileSize { return size }
    let attributes = try FileManager.default.attributesOfItem(atPath: url.path)
    return attributes[.size] as? Int ?? 0
}

private func pngData(from image: NSImage) -> Data? {
    guard let tiffData = image.tiffRepresentation else { return nil }
    return pngData(fromImageData: tiffData)
}

private func pngData(fromImageData data: Data) -> Data? {
    guard let bitmap = NSBitmapImageRep(data: data) else { return nil }
    return bitmap.representation(using: .png, properties: [:])
}

private func mediaType(forFileExtension fileExtension: String) -> String {
    let trimmed = fileExtension.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !trimmed.isEmpty else { return "application/octet-stream" }
    return UTType(filenameExtension: trimmed)?.preferredMIMEType ?? "application/octet-stream"
}
