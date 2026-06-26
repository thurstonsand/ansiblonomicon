package cmd

import (
	"encoding/json"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

// writeRecord drops a recovery record into a tool subdir under the test state root.
func writeTestRecord(t *testing.T, root, tool string, rec Record) {
	t.Helper()
	dir := filepath.Join(root, "session-recovery", tool)
	if err := os.MkdirAll(dir, 0o700); err != nil {
		t.Fatal(err)
	}
	rec.Tool = tool
	body, err := json.Marshal(rec)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, rec.SessionID+".json"), append(body, '\n'), 0o600); err != nil {
		t.Fatal(err)
	}
}

// fakeTool installs a stub executable on PATH that records its working
// directory and arguments to a marker file, proving how resume invokes it.
func fakeTool(t *testing.T, name, marker string) {
	t.Helper()
	if runtime.GOOS == "windows" {
		t.Skip("resume exec proof is unix-only")
	}
	binDir := t.TempDir()
	script := "#!/bin/sh\nprintf '%s|%s' \"$PWD\" \"$*\" > \"" + marker + "\"\n"
	path := filepath.Join(binDir, name)
	if err := os.WriteFile(path, []byte(script), 0o755); err != nil { //nolint:gosec // test stub must be executable
		t.Fatal(err)
	}
	t.Setenv("PATH", binDir+string(os.PathListSeparator)+os.Getenv("PATH"))
}

// TestResumeExecsToolInRecordedDir proves the end-to-end resume path: an
// orphaned record resolves by id, and the owning tool is launched with the
// right args in the record's cwd — even when that cwd is not the current dir.
func TestResumeExecsToolInRecordedDir(t *testing.T) {
	root := t.TempDir()
	t.Setenv("XDG_STATE_HOME", root)

	here := t.TempDir()
	elsewhere := t.TempDir()
	t.Chdir(here)
	boot := currentBoot()
	marker := filepath.Join(t.TempDir(), "invoked")
	fakeTool(t, "pi", marker)

	// Orphaned (prior boot) pi session that lives in a *different* directory.
	writeTestRecord(t, root, "pi", Record{
		SessionID: "019e-target", Name: "fix parser", Cwd: elsewhere,
		PID: 999999, BootID: "PRIOR-BOOT", UpdatedAt: 10,
	})
	// A live session here that must never be offered or resumed.
	writeTestRecord(t, root, "pi", Record{
		SessionID: "019e-live", Cwd: here, PID: os.Getpid(), BootID: boot, UpdatedAt: 20,
	})

	// resume --all by id should exec pi in the recorded (other) directory.
	if err := runResume(true, []string{"019e-target"}); err != nil {
		t.Fatalf("runResume: %v", err)
	}
	got, err := os.ReadFile(marker)
	if err != nil {
		t.Fatalf("fake pi was not invoked: %v", err)
	}
	cwd, args, _ := strings.Cut(string(got), "|")
	if resolveDir(cwd) != resolveDir(elsewhere) {
		t.Fatalf("pi ran in %q, want recorded cwd %q", cwd, elsewhere)
	}
	if args != "--session 019e-target" {
		t.Fatalf("pi args = %q, want '--session 019e-target'", args)
	}
}

// TestResumeRefusesLiveAndForeignDir proves the scoping guarantees: a live
// session is never resumable, and current-dir scope hides other directories.
func TestResumeRefusesLiveAndForeignDir(t *testing.T) {
	root := t.TempDir()
	t.Setenv("XDG_STATE_HOME", root)
	here := t.TempDir()
	elsewhere := t.TempDir()
	t.Chdir(here)
	boot := currentBoot()

	writeTestRecord(t, root, "pi", Record{
		SessionID: "live", Cwd: here, PID: os.Getpid(), BootID: boot, UpdatedAt: 1,
	})
	writeTestRecord(t, root, "pi", Record{
		SessionID: "foreign", Cwd: elsewhere, PID: 999999, BootID: "PRIOR", UpdatedAt: 2,
	})

	if err := runResume(false, []string{"live"}); err == nil {
		t.Fatal("resuming a live session should fail")
	}
	if err := runResume(false, []string{"foreign"}); err == nil {
		t.Fatal("resuming a foreign-dir session without --all should fail")
	}
}
