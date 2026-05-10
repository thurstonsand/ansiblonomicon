// Package protocol defines the JSON contract between ghostty-nav and ghostty-navd.
package protocol

// Envelope contains fields common to every daemon request.
type Envelope struct {
	Command string `json:"command"`
	Reply   bool   `json:"reply"`
}

// WantsReply reports whether the client expects a daemon response.
func (e Envelope) WantsReply() bool {
	return e.Reply
}

// Request is implemented by every concrete command request.
type Request interface {
	WantsReply() bool
}

// ResizeAmount represents exactly one resize amount variant.
type ResizeAmount struct {
	Pixels  *int     `json:"pixels,omitempty"`
	Percent *float64 `json:"percent,omitempty"`
}

// PingRequest checks daemon reachability.
type PingRequest struct {
	Envelope
}

// TerminalIDRequest asks the daemon to resolve the focused Ghostty terminal id.
type TerminalIDRequest struct {
	Envelope
	TTY string `json:"tty,omitempty"`
}

// TabTerminalCountRequest asks for the terminal count in the selected Ghostty tab.
type TabTerminalCountRequest struct {
	Envelope
}

// ClearCacheRequest removes one TTY mapping, or all mappings when TTY is empty.
type ClearCacheRequest struct {
	Envelope
	TTY string `json:"tty,omitempty"`
}

// ActivateRequest activates a Ghostty key table for the caller TTY.
type ActivateRequest struct {
	Envelope
	TTY   string `json:"tty"`
	Table string `json:"table"`
}

// DeactivateRequest deactivates the current Ghostty key table for the caller TTY.
type DeactivateRequest struct {
	Envelope
	TTY string `json:"tty"`
}

// MoveRequest moves Ghostty focus in a direction for the caller TTY.
type MoveRequest struct {
	Envelope
	TTY       string `json:"tty"`
	Direction string `json:"direction"`
}

// SplitRequest creates a Ghostty split from the caller TTY terminal.
type SplitRequest struct {
	Envelope
	TTY         string `json:"tty"`
	Direction   string `json:"direction"`
	CWD         string `json:"cwd,omitempty"`
	CommandText string `json:"commandText,omitempty"`
	Focus       string `json:"focus,omitempty"`
}

// ResizeRequest resizes a Ghostty split adjacent to the caller TTY terminal.
type ResizeRequest struct {
	Envelope
	TTY       string       `json:"tty"`
	Direction string       `json:"direction"`
	Amount    ResizeAmount `json:"amount"`
}

// ToggleZoomRequest toggles split zoom for the caller TTY terminal.
type ToggleZoomRequest struct {
	Envelope
	TTY string `json:"tty"`
}

// PasteRequest asks the daemon to read the local clipboard for text or file-like content.
type PasteRequest struct {
	Envelope
	TTY string `json:"tty,omitempty"`
}

// PasteKind is the paste response variant.
type PasteKind string

const (
	// PasteKindText carries plain clipboard text in Text.
	PasteKindText PasteKind = "text"
	// PasteKindFiles carries one or more materialized file entries in Files.
	PasteKindFiles PasteKind = "files"
)

// PasteFile is one file-like clipboard item returned by the daemon or written by the client.
type PasteFile struct {
	Path      string `json:"path,omitempty"`
	FileName  string `json:"fileName,omitempty"`
	MediaType string `json:"mediaType,omitempty"`
	Bytes     int64  `json:"bytes,omitempty"`
	Source    string `json:"source,omitempty"`
}

// PasteHeader is the JSON header sent before any streamed paste bytes.
type PasteHeader struct {
	Response
	Kind  PasteKind   `json:"kind,omitempty"`
	Text  string      `json:"text,omitempty"`
	Files []PasteFile `json:"files,omitempty"`
	Bytes int64       `json:"bytes,omitempty"`
}

// PasteResponse is a validated paste response returned by the client after file materialization.
type PasteResponse interface {
	PasteKind() PasteKind
}

// PasteTextResponse is a text paste response.
type PasteTextResponse struct {
	Text string
}

// PasteKind reports the response variant.
func (PasteTextResponse) PasteKind() PasteKind {
	return PasteKindText
}

// PasteFilesResponse is a file paste response.
type PasteFilesResponse struct {
	Files []PasteFile
	Bytes int64
}

// PasteKind reports the response variant.
func (PasteFilesResponse) PasteKind() PasteKind {
	return PasteKindFiles
}

// Response is the daemon response for requests with Reply set. Empty Error means success.
type Response struct {
	Value string `json:"value,omitempty"`
	Error string `json:"error,omitempty"`
}
