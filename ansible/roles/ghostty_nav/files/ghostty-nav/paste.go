package main

import (
	"bufio"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"mime"
	"os"
	"path/filepath"
	"strings"

	"house.thurstons/ghostty-nav/internal/client"
	"house.thurstons/ghostty-nav/internal/protocol"
)

const noPasteContentExitCode = 2

type exitError struct {
	code int
	err  error
}

func (e exitError) Error() string {
	return e.err.Error()
}

func runPaste(out io.Writer, opts *options, outputDir string, jsonOutput bool) error {
	if strings.TrimSpace(outputDir) == "" {
		return errors.New("--output-dir is required")
	}
	ttyValue := ""
	if value, err := requestTTY(opts); err == nil {
		ttyValue = value
	}

	response, err := receivePaste(
		client.SocketPath(),
		protocol.PasteRequest{Envelope: protocol.Envelope{Command: "paste", Reply: true}, TTY: ttyValue},
		outputDir,
	)
	if err != nil {
		return err
	}

	if jsonOutput {
		return printPasteJSON(out, response)
	}

	_, err = fmt.Fprintln(out, pasteText(response))
	return err
}

func receivePaste(socketPath string, request protocol.PasteRequest, outputDir string) (protocol.PasteResponse, error) {
	conn, err := client.Dial(socketPath)
	if err != nil {
		return nil, err
	}
	defer func() { _ = conn.Close() }()

	if err := client.WriteRequest(conn, request); err != nil {
		return nil, err
	}

	receiver := pasteReceiver{reader: bufio.NewReader(conn), outputDir: outputDir}
	return receiver.receive()
}

type pasteReceiver struct {
	reader    *bufio.Reader
	outputDir string
}

func (r pasteReceiver) receive() (protocol.PasteResponse, error) {
	header, err := r.readHeader()
	if err != nil {
		return nil, err
	}
	if header.Error != "" {
		return nil, fmt.Errorf("%s", header.Error)
	}

	switch header.Kind {
	case protocol.PasteKindText:
		return protocol.PasteTextResponse{Text: header.Text}, nil
	case protocol.PasteKindFiles:
		files, err := r.receiveFiles(header.Files)
		if err != nil {
			return nil, err
		}
		return protocol.PasteFilesResponse{Files: files, Bytes: sumPasteFileBytes(files)}, nil
	case "":
		return nil, exitError{code: noPasteContentExitCode, err: errors.New("clipboard has no supported content")}
	default:
		return nil, fmt.Errorf("unsupported paste response kind: %s", header.Kind)
	}
}

func (r pasteReceiver) readHeader() (protocol.PasteHeader, error) {
	line, err := r.reader.ReadBytes('\n')
	if err != nil {
		return protocol.PasteHeader{}, fmt.Errorf("read paste header: %w", err)
	}

	var header protocol.PasteHeader
	if err := json.Unmarshal(line, &header); err != nil {
		return protocol.PasteHeader{}, fmt.Errorf("decode paste header: %w", err)
	}
	return header, nil
}

func (r pasteReceiver) receiveFiles(files []protocol.PasteFile) ([]protocol.PasteFile, error) {
	materializedFiles := make([]protocol.PasteFile, 0, len(files))
	for _, file := range files {
		materialized, err := materializePasteFile(r.reader, file, r.outputDir)
		if err != nil {
			return nil, err
		}
		materializedFiles = append(materializedFiles, materialized)
	}
	return materializedFiles, nil
}

func materializePasteFile(reader io.Reader, file protocol.PasteFile, outputDir string) (protocol.PasteFile, error) {
	if file.Bytes < 0 {
		return protocol.PasteFile{}, fmt.Errorf("clipboard file %s has invalid byte count", file.FileName)
	}
	if err := os.MkdirAll(outputDir, 0o700); err != nil {
		return protocol.PasteFile{}, fmt.Errorf("create output directory: %w", err)
	}
	path := filepath.Join(outputDir, uniquePasteFileName(file))
	out, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o600)
	if err != nil {
		return protocol.PasteFile{}, fmt.Errorf("create clipboard file: %w", err)
	}
	_, copyErr := io.CopyN(out, reader, file.Bytes)
	closeErr := out.Close()
	if copyErr != nil {
		_ = os.Remove(path)
		return protocol.PasteFile{}, fmt.Errorf("write clipboard file: %w", copyErr)
	}
	if closeErr != nil {
		_ = os.Remove(path)
		return protocol.PasteFile{}, fmt.Errorf("close clipboard file: %w", closeErr)
	}
	file.Path = path
	return file, nil
}

func uniquePasteFileName(file protocol.PasteFile) string {
	ext := extensionForPasteFile(file)
	name := strings.TrimSpace(filepath.Base(file.FileName))
	if name != "." && name != string(filepath.Separator) && name != "" {
		base := strings.TrimSuffix(name, filepath.Ext(name))
		if base != "" {
			return fmt.Sprintf("%s-%s%s", sanitizeFilenameBase(base), randomSuffix(), ext)
		}
	}
	return fmt.Sprintf("pi-paste-%s%s", randomSuffix(), ext)
}

func extensionForPasteFile(file protocol.PasteFile) string {
	if ext := filepath.Ext(file.FileName); ext != "" {
		return ext
	}
	if file.FileName != "" {
		return ""
	}
	if exts, err := mime.ExtensionsByType(file.MediaType); err == nil && len(exts) > 0 {
		return exts[0]
	}
	return ""
}

func sanitizeFilenameBase(value string) string {
	var builder strings.Builder
	for _, r := range value {
		switch {
		case r >= 'a' && r <= 'z', r >= 'A' && r <= 'Z', r >= '0' && r <= '9', r == '-', r == '_', r == '.':
			builder.WriteRune(r)
		default:
			builder.WriteRune('-')
		}
	}
	result := strings.Trim(builder.String(), ".-")
	if result == "" {
		return "pi-paste"
	}
	return result
}

func randomSuffix() string {
	bytes := make([]byte, 6)
	if _, err := rand.Read(bytes); err != nil {
		return "fallback"
	}
	return hex.EncodeToString(bytes)
}

func pasteText(response protocol.PasteResponse) string {
	switch typed := response.(type) {
	case protocol.PasteTextResponse:
		return typed.Text
	case protocol.PasteFilesResponse:
		paths := make([]string, 0, len(typed.Files))
		for _, file := range typed.Files {
			paths = append(paths, file.Path)
		}
		return strings.Join(paths, " ")
	default:
		return ""
	}
}

func printPasteJSON(out io.Writer, response protocol.PasteResponse) error {
	encoded, err := json.Marshal(toPasteHeader(response))
	if err != nil {
		return fmt.Errorf("encode paste response: %w", err)
	}
	_, err = fmt.Fprintln(out, string(encoded))
	return err
}

func toPasteHeader(response protocol.PasteResponse) protocol.PasteHeader {
	switch typed := response.(type) {
	case protocol.PasteTextResponse:
		return protocol.PasteHeader{Kind: protocol.PasteKindText, Text: typed.Text}
	case protocol.PasteFilesResponse:
		return protocol.PasteHeader{Kind: protocol.PasteKindFiles, Files: typed.Files, Bytes: typed.Bytes}
	default:
		return protocol.PasteHeader{}
	}
}

func sumPasteFileBytes(files []protocol.PasteFile) int64 {
	var total int64
	for _, file := range files {
		total += file.Bytes
	}
	return total
}
