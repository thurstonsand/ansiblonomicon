package cmd

import (
	"fmt"
	"os"
	"text/tabwriter"

	"github.com/spf13/cobra"
)

func newListCmd() *cobra.Command {
	var all bool

	cmd := &cobra.Command{
		Use:     "list",
		Aliases: []string{"ls"},
		Short:   "List live and orphaned sessions",
		Long:    "List sessions that opened and have not cleanly shut down, each labeled live (open now) or orphaned (not closed properly). Defaults to the current directory; use --all for every directory.",
		Args:    cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			return runList(cmd, all)
		},
	}
	cmd.Flags().BoolVarP(&all, "all", "a", false, "List sessions across all directories")
	return cmd
}

func runList(cmd *cobra.Command, all bool) error {
	records, err := loadRecords()
	if err != nil {
		return err
	}
	boot := currentBoot()
	cwd, _ := os.Getwd()

	var shown []Record
	for _, rec := range records {
		if rec.deleted() || (!all && !sameDir(rec.Cwd, cwd)) {
			continue
		}
		shown = append(shown, rec)
	}

	out := cmd.OutOrStdout()
	if len(shown) == 0 {
		_, _ = fmt.Fprintln(out, "No tracked sessions.")
		return nil
	}

	w := tabwriter.NewWriter(out, 0, 0, 2, ' ', 0)
	header := "STATUS\tTOOL\tNAME\tSESSION"
	if all {
		header += "\tDIR"
	}
	if _, err := fmt.Fprintln(w, header); err != nil {
		return err
	}
	for _, rec := range shown {
		row := fmt.Sprintf("%s\t%s\t%s\t%s", rec.status(boot), rec.Tool, truncate(rec.Name, 48), rec.SessionID)
		if all {
			row += "\t" + shortenHome(rec.Cwd)
		}
		if _, err := fmt.Fprintln(w, row); err != nil {
			return err
		}
	}
	return w.Flush()
}

func truncate(s string, n int) string {
	if s == "" {
		return "-"
	}
	if len(s) <= n {
		return s
	}
	return s[:n-1] + "…"
}

func shortenHome(path string) string {
	home, err := os.UserHomeDir()
	if err != nil || home == "" || path == "" {
		return path
	}
	if path == home {
		return "~"
	}
	if len(path) > len(home) && path[:len(home)] == home && path[len(home)] == os.PathSeparator {
		return "~" + path[len(home):]
	}
	return path
}
