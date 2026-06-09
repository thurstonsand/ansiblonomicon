// Package cmd implements the sessions CLI: list and resume agent sessions that
// were live at the last shutdown, read from the shared recovery tree.
package cmd

import "github.com/spf13/cobra"

// NewRootCmd builds the sessions command tree.
func NewRootCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:           "sessions",
		Short:         "List and resume agent sessions after a restart",
		Long:          "List live and orphaned Pi and Claude Code sessions, and resume the ones that were not closed cleanly.",
		SilenceUsage:  true,
		SilenceErrors: true,
	}
	cmd.AddCommand(newListCmd())
	cmd.AddCommand(newResumeCmd())
	cmd.AddCommand(newPruneCmd())
	cmd.AddCommand(newShellCmd())
	return cmd
}
