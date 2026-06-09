package cmd

import (
	"errors"
	"fmt"
	"os"
	"os/exec"

	"github.com/spf13/cobra"
)

func newResumeCmd() *cobra.Command {
	var all bool

	cmd := &cobra.Command{
		Use:               "resume [name|id]",
		Aliases:           []string{"r"},
		Short:             "Resume an orphaned session",
		Long:              "Resume a session that was not closed cleanly, by name or id. Completion and matching cover the current directory by default, or every directory with --all. Live sessions (open elsewhere) and clean historical sessions are never offered.",
		Args:              cobra.MaximumNArgs(1),
		ValidArgsFunction: completeOrphans,
		RunE: func(_ *cobra.Command, args []string) error {
			return runResume(all, args)
		},
	}
	cmd.Flags().BoolVarP(&all, "all", "a", false, "Match orphaned sessions across all directories")
	return cmd
}

func runResume(all bool, args []string) error {
	records, err := loadRecords()
	if err != nil {
		return err
	}
	cwd, _ := os.Getwd()
	candidates := scopedOrphans(records, currentBoot(), cwd, all)
	if len(candidates) == 0 {
		return errors.New("no orphaned sessions to resume")
	}

	var target Record
	if len(args) == 0 {
		if len(candidates) > 1 {
			return fmt.Errorf("%d orphaned sessions; specify a name or id", len(candidates))
		}
		target = candidates[0]
	} else {
		target, err = resolve(candidates, args[0])
		if err != nil {
			return fmt.Errorf("%w: %q", err, args[0])
		}
	}

	argv, err := resumeArgv(target)
	if err != nil {
		return err
	}
	bin, err := execLookPath(argv[0])
	if err != nil {
		return fmt.Errorf("cannot find %s on PATH: %w", argv[0], err)
	}

	run := exec.Command(bin, argv[1:]...) //nolint:gosec // argv is built from a fixed verb table
	run.Dir = target.Cwd
	run.Stdin, run.Stdout, run.Stderr = os.Stdin, os.Stdout, os.Stderr
	return run.Run()
}

func completeOrphans(cmd *cobra.Command, args []string, _ string) ([]string, cobra.ShellCompDirective) {
	if len(args) > 0 {
		return nil, cobra.ShellCompDirectiveNoFileComp
	}
	all, _ := cmd.Flags().GetBool("all")
	records, err := loadRecords()
	if err != nil {
		return nil, cobra.ShellCompDirectiveError
	}
	cwd, _ := os.Getwd()
	candidates := scopedOrphans(records, currentBoot(), cwd, all)

	completions := make([]string, 0, len(candidates))
	for _, rec := range candidates {
		desc := rec.Tool
		if rec.Name != "" {
			desc += " · " + rec.Name
		}
		if all {
			desc += " · " + shortenHome(rec.Cwd)
		}
		value := rec.SessionID
		if rec.Name != "" {
			value = rec.Name
		}
		completions = append(completions, value+"\t"+desc)
	}
	return completions, cobra.ShellCompDirectiveNoFileComp
}
