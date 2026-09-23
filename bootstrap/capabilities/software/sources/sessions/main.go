// Command sessions lists and resumes agent sessions that were live when the
// machine last went down. It reads the shared recovery tree written by the Pi
// and Claude Code recorders and never touches transcripts or native stores.
package main

import (
	"fmt"
	"os"

	"house.thurstons/sessions/internal/cmd"
)

func main() {
	if err := cmd.NewRootCmd().Execute(); err != nil {
		fmt.Fprintln(os.Stderr, "sessions:", err)
		os.Exit(1)
	}
}
