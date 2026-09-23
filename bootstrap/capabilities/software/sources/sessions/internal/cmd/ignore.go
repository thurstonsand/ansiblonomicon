package cmd

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"

	"github.com/spf13/cobra"
)

func newIgnoreCmd() *cobra.Command {
	var remove bool

	cmd := &cobra.Command{
		Use:   "ignore [path]",
		Short: "Manage ignored session directories",
		Long:  "Add or remove recursively ignored session directories. With no arguments, prune existing records using the current config.",
		Args: func(_ *cobra.Command, args []string) error {
			if len(args) > 1 {
				return errors.New("requires at most one path")
			}
			if remove && len(args) == 0 {
				return errors.New("--rm requires a path")
			}
			return nil
		},
		RunE: func(cmd *cobra.Command, args []string) error {
			return runIgnore(cmd, args, remove)
		},
	}
	cmd.Flags().BoolVar(&remove, "rm", false, "remove an ignored directory")
	return cmd
}

func runIgnore(cmd *cobra.Command, args []string, remove bool) error {
	cfg := loadConfig()
	out := cmd.OutOrStdout()

	if len(args) > 0 {
		dir := normalizeConfigDir(args[0])
		if remove {
			cfg = cfg.withoutIgnoredDir(dir)
			if err := saveConfig(cfg); err != nil {
				return err
			}
			_, _ = fmt.Fprintf(out, "Removed ignored directory %s.\n", dir)
			return nil
		}
		if !cfg.hasIgnoredDir(dir) {
			cfg.IgnoredDirectories = append(cfg.IgnoredDirectories, dir)
			if err := saveConfig(cfg); err != nil {
				return err
			}
		}
	}

	removed, err := pruneIgnoredRecords(cfg)
	if err != nil {
		return err
	}
	_, _ = fmt.Fprintf(out, "Pruned %d ignored record(s).\n", removed)
	if len(args) == 0 {
		for _, dir := range cfg.IgnoredDirectories {
			if _, err := fmt.Fprintln(out, dir); err != nil {
				return err
			}
		}
	}
	return nil
}

func pruneIgnoredRecords(cfg config) (int, error) {
	removed := 0
	for _, tool := range tools {
		dir := filepath.Join(stateRoot(), tool)
		entries, err := os.ReadDir(dir)
		if err != nil {
			if errors.Is(err, os.ErrNotExist) {
				continue
			}
			return removed, err
		}
		for _, entry := range entries {
			if entry.IsDir() || filepath.Ext(entry.Name()) != ".json" {
				continue
			}
			path := filepath.Join(dir, entry.Name())
			data, err := os.ReadFile(path)
			if err != nil {
				continue
			}
			var rec Record
			if err := json.Unmarshal(data, &rec); err != nil || rec.SessionID == "" {
				continue
			}
			if cfg.tracks(rec.Cwd) {
				continue
			}
			if err := os.Remove(path); err != nil && !errors.Is(err, os.ErrNotExist) {
				return removed, err
			}
			removed++
		}
	}
	return removed, nil
}
