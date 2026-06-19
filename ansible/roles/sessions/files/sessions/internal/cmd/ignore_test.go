package cmd

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/spf13/cobra"
)

func ignoreTestCmd(out *bytes.Buffer) *cobra.Command {
	cmd := &cobra.Command{}
	cmd.SetOut(out)
	return cmd
}

func TestIgnoreAddsDirectoryAndPrunesExistingRecords(t *testing.T) {
	root := t.TempDir()
	configRoot := t.TempDir()
	ignored := t.TempDir()
	ignoredChild := filepath.Join(ignored, "child")
	if err := os.MkdirAll(ignoredChild, 0o700); err != nil {
		t.Fatal(err)
	}
	tracked := t.TempDir()
	t.Setenv("XDG_STATE_HOME", root)
	t.Setenv("XDG_CONFIG_HOME", configRoot)

	writeTestRecord(t, root, "claude", Record{SessionID: "ignored", Cwd: ignoredChild, UpdatedAt: 2})
	writeTestRecord(t, root, "claude", Record{SessionID: "tracked", Cwd: tracked, UpdatedAt: 1})

	var out bytes.Buffer
	if err := runIgnore(ignoreTestCmd(&out), []string{ignored}, false); err != nil {
		t.Fatal(err)
	}

	cfg := loadConfig()
	if len(cfg.IgnoredDirectories) != 1 || cfg.IgnoredDirectories[0] != normalizeConfigDir(ignored) {
		t.Fatalf("ignored directories = %#v", cfg.IgnoredDirectories)
	}
	if !strings.Contains(out.String(), "Pruned 1 ignored record") {
		t.Fatalf("output = %q", out.String())
	}
	if _, err := os.Stat(filepath.Join(root, "session-recovery", "claude", "ignored.json")); !os.IsNotExist(err) {
		t.Fatalf("ignored record still exists: %v", err)
	}
	if _, err := os.Stat(filepath.Join(root, "session-recovery", "claude", "tracked.json")); err != nil {
		t.Fatalf("tracked record missing: %v", err)
	}
}

func TestIgnoreNoArgsPrunesManualConfig(t *testing.T) {
	root := t.TempDir()
	configRoot := t.TempDir()
	ignored := t.TempDir()
	ignoredChild := filepath.Join(ignored, "child")
	if err := os.MkdirAll(ignoredChild, 0o700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("XDG_STATE_HOME", root)
	t.Setenv("XDG_CONFIG_HOME", configRoot)

	cfg := config{IgnoredDirectories: []string{ignored}}
	if err := saveConfig(cfg); err != nil {
		t.Fatal(err)
	}
	writeTestRecord(t, root, "claude", Record{SessionID: "ignored", Cwd: ignoredChild, UpdatedAt: 1})

	var out bytes.Buffer
	if err := runIgnore(ignoreTestCmd(&out), nil, false); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out.String(), "Pruned 1 ignored record") {
		t.Fatalf("output = %q", out.String())
	}
	if !strings.Contains(out.String(), ignored) {
		t.Fatalf("output did not list ignored directory: %q", out.String())
	}
}

func TestIgnoreRemove(t *testing.T) {
	configRoot := t.TempDir()
	ignored := t.TempDir()
	t.Setenv("XDG_CONFIG_HOME", configRoot)

	if err := saveConfig(config{IgnoredDirectories: []string{ignored}}); err != nil {
		t.Fatal(err)
	}

	var rmOut bytes.Buffer
	if err := runIgnore(ignoreTestCmd(&rmOut), []string{ignored}, true); err != nil {
		t.Fatal(err)
	}
	if got := loadConfig().IgnoredDirectories; len(got) != 0 {
		t.Fatalf("ignored directories after rm = %#v", got)
	}
}
