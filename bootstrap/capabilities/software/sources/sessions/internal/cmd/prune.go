package cmd

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/spf13/cobra"
)

func newPruneCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:               "prune [name|id]",
		Short:             "Hide records left over from a prior boot",
		Long:              "Without an argument, hide recovery records whose boot id differs from the current boot; records from the current boot are left untouched. With a name or id, hide only that session's record, regardless of boot. Hidden records stay in history and can still be resumed by name or id.",
		Args:              cobra.MaximumNArgs(1),
		ValidArgsFunction: completeRecords,
		RunE:              runPrune,
	}
	return cmd
}

func runPrune(cmd *cobra.Command, args []string) error {
	records, err := loadRecords()
	if err != nil {
		return err
	}
	if len(args) > 0 {
		return pruneOne(cmd, records, args[0])
	}
	return prunePriorBoot(cmd, records)
}

func pruneOne(cmd *cobra.Command, records []Record, arg string) error {
	boot := currentBoot()
	orphans := scopedOrphans(records, boot, "", true)
	target, err := resolve(orphans, arg)
	if err != nil {
		if live, lerr := resolve(liveRecords(records, boot), arg); lerr == nil {
			return fmt.Errorf("%s is live; cannot prune an open session", recordLabel(live))
		}
		return fmt.Errorf("%w: %q", err, arg)
	}
	if err := softDeleteRecord(target); err != nil {
		return err
	}
	_, _ = fmt.Fprintf(cmd.OutOrStdout(), "Pruned %s.\n", recordLabel(target))
	return nil
}

func liveRecords(records []Record, boot string) []Record {
	out := make([]Record, 0, len(records))
	for _, rec := range records {
		if !rec.deleted() && rec.live(boot) {
			out = append(out, rec)
		}
	}
	return out
}

func prunePriorBoot(cmd *cobra.Command, records []Record) error {
	boot := currentBoot()
	removed := 0
	for _, rec := range records {
		if rec.deleted() || (boot != "" && rec.BootID == boot) {
			continue
		}
		if err := softDeleteRecord(rec); err != nil {
			return err
		}
		removed++
	}
	_, _ = fmt.Fprintf(cmd.OutOrStdout(), "Pruned %d prior-boot record(s).\n", removed)
	return nil
}

func softDeleteRecord(rec Record) error {
	if rec.deleted() {
		return nil
	}
	rec.DeletedAt = time.Now().UnixMilli()
	path := filepath.Join(stateRoot(), rec.Tool, rec.SessionID+".json")
	data, err := json.MarshalIndent(rec, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(data, '\n'), 0o600)
}

func recordLabel(rec Record) string {
	if rec.Name != "" {
		return rec.Name
	}
	return rec.SessionID
}

func completeRecords(_ *cobra.Command, args []string, _ string) ([]string, cobra.ShellCompDirective) {
	if len(args) > 0 {
		return nil, cobra.ShellCompDirectiveNoFileComp
	}
	records, err := loadRecords()
	if err != nil {
		return nil, cobra.ShellCompDirectiveError
	}
	orphans := scopedOrphans(records, currentBoot(), "", true)
	completions := make([]string, 0, len(orphans))
	for _, rec := range orphans {
		desc := rec.Tool
		if rec.Name != "" {
			desc += " · " + rec.Name
		}
		desc += " · " + shortenHome(rec.Cwd)
		value := rec.SessionID
		if rec.Name != "" {
			value = rec.Name
		}
		completions = append(completions, value+"\t"+desc)
	}
	return completions, cobra.ShellCompDirectiveNoFileComp
}
