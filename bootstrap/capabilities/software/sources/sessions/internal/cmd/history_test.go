package cmd

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/spf13/cobra"
)

func outputCmd(out *bytes.Buffer) *cobra.Command {
	cmd := &cobra.Command{}
	cmd.SetOut(out)
	return cmd
}

func TestListHidesDeletedRecords(t *testing.T) {
	root := t.TempDir()
	t.Setenv("XDG_STATE_HOME", root)
	here := t.TempDir()
	t.Chdir(here)

	writeTestRecord(t, root, "pi", Record{SessionID: "visible", Cwd: here, BootID: "PRIOR", UpdatedAt: 2})
	writeTestRecord(t, root, "pi", Record{SessionID: "hidden", Cwd: here, BootID: "PRIOR", UpdatedAt: 1, DeletedAt: 3})

	var out bytes.Buffer
	if err := runList(outputCmd(&out), false); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out.String(), "visible") || strings.Contains(out.String(), "hidden") {
		t.Fatalf("list output = %q", out.String())
	}
}

func TestResumeExplicitNameFindsDeletedHistory(t *testing.T) {
	root := t.TempDir()
	t.Setenv("XDG_STATE_HOME", root)
	here := t.TempDir()
	elsewhere := t.TempDir()
	t.Chdir(here)
	marker := filepath.Join(t.TempDir(), "invoked")
	fakeTool(t, "pi", marker)

	writeTestRecord(t, root, "pi", Record{
		SessionID: "historical", Name: "old mission", Cwd: elsewhere,
		PID: 999999, BootID: "PRIOR", UpdatedAt: 1, DeletedAt: 2,
	})

	if err := runResume(false, []string{"old mission"}); err != nil {
		t.Fatalf("runResume: %v", err)
	}
	got, err := os.ReadFile(marker)
	if err != nil {
		t.Fatalf("fake pi was not invoked: %v", err)
	}
	if !strings.Contains(string(got), "--session historical") {
		t.Fatalf("pi invocation = %q", string(got))
	}
}

func TestPruneSoftDeletesPriorBootRecords(t *testing.T) {
	root := t.TempDir()
	t.Setenv("XDG_STATE_HOME", root)

	writeTestRecord(t, root, "pi", Record{SessionID: "old", Cwd: t.TempDir(), BootID: "PRIOR", UpdatedAt: 1})

	var out bytes.Buffer
	if err := prunePriorBoot(outputCmd(&out), mustLoadRecords(t)); err != nil {
		t.Fatal(err)
	}

	path := filepath.Join(root, "session-recovery", "pi", "old.json")
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("record was removed instead of hidden: %v", err)
	}
	var rec Record
	if err := json.Unmarshal(data, &rec); err != nil {
		t.Fatal(err)
	}
	if rec.DeletedAt == 0 {
		t.Fatalf("deletedAt was not set: %+v", rec)
	}
}

func mustLoadRecords(t *testing.T) []Record {
	t.Helper()
	records, err := loadRecords()
	if err != nil {
		t.Fatal(err)
	}
	return records
}
