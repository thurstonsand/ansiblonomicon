package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
)

// newShellCmd emits shell integration for sessions,
// which is just the Cobra completion script.
// Loaded with `eval "$(sessions shell zsh)"`.
func newShellCmd() *cobra.Command {
	return &cobra.Command{
		Use:       "shell <shell>",
		Short:     "Output shell integration",
		ValidArgs: []string{"bash", "zsh"},
		Long: `Output shell integration script for the specified shell.

Usage:
  eval "$(sessions shell zsh)"

Add to your shell's rc file for persistent integration.`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			out := cmd.OutOrStdout()
			switch args[0] {
			case "bash":
				return cmd.Root().GenBashCompletion(out)
			case "zsh":
				return cmd.Root().GenZshCompletion(out)
			default:
				return fmt.Errorf("unsupported shell: %s", args[0])
			}
		},
	}
}
