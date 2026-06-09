package cmd

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/spf13/cobra"
)

func newPruneCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "prune",
		Short: "Delete records left over from a prior boot",
		Long:  "Delete recovery records whose boot id differs from the current boot. Records from the current boot are left untouched.",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			return runPrune(cmd)
		},
	}
}

func runPrune(cmd *cobra.Command) error {
	records, err := loadRecords()
	if err != nil {
		return err
	}
	boot := currentBoot()
	root := stateRoot()
	removed := 0
	for _, rec := range records {
		if boot != "" && rec.BootID == boot {
			continue
		}
		path := filepath.Join(root, rec.Tool, rec.SessionID+".json")
		if err := os.Remove(path); err != nil && !os.IsNotExist(err) {
			return err
		}
		removed++
	}
	_, _ = fmt.Fprintf(cmd.OutOrStdout(), "Pruned %d prior-boot record(s).\n", removed)
	return nil
}
