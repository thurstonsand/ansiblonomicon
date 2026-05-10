// Package tty resolves terminal device paths for daemon requests.
package tty

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
)

// Normalize returns value as an absolute /dev path.
func Normalize(value string) string {
	if len(value) >= 5 && value[:5] == "/dev/" {
		return value
	}
	return "/dev/" + value
}

// Current returns the path for the controlling terminal.
func Current() (string, error) {
	file, err := os.OpenFile("/dev/tty", os.O_RDONLY, 0)
	if err != nil {
		return "", fmt.Errorf("open /dev/tty: %w", err)
	}
	defer func() { _ = file.Close() }()

	fd := file.Fd()
	candidates := []string{
		fmt.Sprintf("/dev/fd/%d", fd),
		fmt.Sprintf("/proc/self/fd/%d", fd),
	}
	for _, candidate := range candidates {
		path, err := os.Readlink(candidate)
		if err == nil && path != "" {
			if !filepath.IsAbs(path) {
				return Normalize(path), nil
			}
			return path, nil
		}
	}
	return "", errors.New("resolve controlling tty path")
}
