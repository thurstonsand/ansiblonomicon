package cmd

import (
	"errors"
	"os"
	"testing"
)

func TestLiveRequiresMatchingBootAndAlivePID(t *testing.T) {
	self := os.Getpid()
	cases := []struct {
		name string
		rec  Record
		boot string
		want bool
	}{
		{"current boot, alive pid", Record{BootID: "b1", PID: self}, "b1", true},
		{"prior boot, alive pid", Record{BootID: "b0", PID: self}, "b1", false},
		{"current boot, dead pid", Record{BootID: "b1", PID: 1 << 30}, "b1", false},
		{"empty boot", Record{BootID: "", PID: self}, "", false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := tc.rec.live(tc.boot); got != tc.want {
				t.Fatalf("live() = %v, want %v", got, tc.want)
			}
		})
	}
}

func TestDedupeLineageKeepsNewestPerProcess(t *testing.T) {
	records := []Record{
		{SessionID: "old", BootID: "b1", PID: 100, UpdatedAt: 10},
		{SessionID: "new", BootID: "b1", PID: 100, UpdatedAt: 20},
		{SessionID: "other", BootID: "b1", PID: 200, UpdatedAt: 5},
	}
	got := dedupeLineage(records)
	if len(got) != 2 {
		t.Fatalf("got %d records, want 2", len(got))
	}
	if got[0].SessionID != "new" {
		t.Fatalf("newest-first ordering broken: %q", got[0].SessionID)
	}
	for _, rec := range got {
		if rec.SessionID == "old" {
			t.Fatal("stale lineage sibling was not dropped")
		}
	}
}

func TestScopedOrphansExcludesLiveAndOtherDirs(t *testing.T) {
	self := os.Getpid()
	cwd, _ := os.Getwd()
	records := []Record{
		{SessionID: "live-here", BootID: "b1", PID: self, Cwd: cwd},
		{SessionID: "orphan-here", BootID: "b0", PID: self, Cwd: cwd},
		{SessionID: "orphan-elsewhere", BootID: "b0", PID: self, Cwd: "/somewhere/else"},
	}

	scoped := scopedOrphans(records, "b1", cwd, false)
	if len(scoped) != 1 || scoped[0].SessionID != "orphan-here" {
		t.Fatalf("current-dir scope = %+v, want only orphan-here", scoped)
	}

	all := scopedOrphans(records, "b1", cwd, true)
	if len(all) != 2 {
		t.Fatalf("all-dir scope = %d, want 2 orphans", len(all))
	}
}

func TestResolvePrefersIDThenName(t *testing.T) {
	candidates := []Record{
		{SessionID: "019e-aaaa", Name: "refactor auth"},
		{SessionID: "019e-bbbb", Name: "fix tests"},
	}

	if rec, err := resolve(candidates, "019e-aaaa"); err != nil || rec.Name != "refactor auth" {
		t.Fatalf("exact id match failed: %+v %v", rec, err)
	}
	if rec, err := resolve(candidates, "fix tests"); err != nil || rec.SessionID != "019e-bbbb" {
		t.Fatalf("name match failed: %+v %v", rec, err)
	}
	if _, err := resolve(candidates, "019e-"); !errors.Is(err, errAmbiguous) {
		t.Fatalf("ambiguous prefix should error, got %v", err)
	}
	if _, err := resolve(candidates, "nope"); !errors.Is(err, errNoMatch) {
		t.Fatalf("missing arg should error, got %v", err)
	}
}

func TestResumeArgvPerTool(t *testing.T) {
	pi, err := resumeArgv(Record{Tool: "pi", SessionID: "abc"})
	if err != nil || pi[0] != "pi" || pi[2] != "abc" {
		t.Fatalf("pi argv = %v %v", pi, err)
	}
	cl, err := resumeArgv(Record{Tool: "claude", SessionID: "xyz"})
	if err != nil || cl[0] != "claude" || cl[1] != "--resume" {
		t.Fatalf("claude argv = %v %v", cl, err)
	}
	if _, err := resumeArgv(Record{Tool: "amp"}); err == nil {
		t.Fatal("unknown tool should error")
	}
}
