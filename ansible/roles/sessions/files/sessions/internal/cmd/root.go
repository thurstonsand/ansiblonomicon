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
	cmd.AddCommand(newIgnoreCmd())
	cmd.AddCommand(newShellCmd())

	cmd.CompletionOptions.HiddenDefaultCmd = true
	// Replace the auto-generated "help" subcommand with a hidden, renamed
	// stand-in. Cobra's usage template force-lists any command literally named
	// "help", so renaming is what actually keeps it out of the listing. The
	// -h/--help flags still print full help for every command.
	cmd.SetHelpCommand(&cobra.Command{Use: "no-help", Hidden: true})
	return cmd
}
