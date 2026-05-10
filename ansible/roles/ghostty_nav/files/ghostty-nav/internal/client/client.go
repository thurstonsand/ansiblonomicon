// Package client sends ghostty-nav requests to the local or forwarded daemon socket.
package client

import (
	"bufio"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"os"
	"path/filepath"

	"house.thurstons/ghostty-nav/internal/protocol"
)

// SocketPath returns the daemon socket path from GHOSTTY_NAV_SOCKET or the user default.
func SocketPath() string {
	if value := os.Getenv("GHOSTTY_NAV_SOCKET"); value != "" {
		return value
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return ""
	}
	return filepath.Join(home, ".local/run/ghostty-nav/ghostty-navd.sock")
}

// Dial connects to a ghostty-navd Unix socket.
func Dial(socketPath string) (*net.UnixConn, error) {
	if socketPath == "" {
		return nil, errors.New("socket path is empty")
	}

	addr := net.UnixAddr{Name: socketPath, Net: "unix"}
	conn, err := net.DialUnix("unix", nil, &addr)
	if err != nil {
		return nil, fmt.Errorf("connect %s: %w", socketPath, err)
	}
	return conn, nil
}

// WriteRequest writes one request to the daemon and closes the write side of the connection.
func WriteRequest(conn *net.UnixConn, request protocol.Request) error {
	if err := json.NewEncoder(conn).Encode(request); err != nil {
		return fmt.Errorf("send request: %w", err)
	}
	if err := conn.CloseWrite(); err != nil {
		return fmt.Errorf("close write: %w", err)
	}
	return nil
}

// Send writes one request to the daemon and reads a response when the request asks for one.
func Send(socketPath string, request protocol.Request) (*protocol.Response, error) {
	conn, err := Dial(socketPath)
	if err != nil {
		return nil, err
	}
	defer func() { _ = conn.Close() }()

	if err := WriteRequest(conn, request); err != nil {
		return nil, err
	}

	reader := bufio.NewReader(conn)
	if !request.WantsReply() {
		// No-reply requests still wait for EOF so the daemon has accepted and processed the request.
		if _, err := reader.ReadByte(); err != nil {
			return &protocol.Response{}, nil
		}
		return nil, errors.New("daemon sent unexpected data for no-reply request")
	}

	var response protocol.Response
	if err := json.NewDecoder(reader).Decode(&response); err != nil {
		return nil, fmt.Errorf("read response: %w", err)
	}
	if response.Error != "" {
		return &response, fmt.Errorf("%s", response.Error)
	}
	return &response, nil
}
