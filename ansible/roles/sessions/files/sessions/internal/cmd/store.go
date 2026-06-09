package cmd

import (
	"encoding/json"
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
	"syscall"
)

// tools are the recovery-tree subdirectories the CLI reads.
var tools = []string{"pi", "claude"}

// Record is one live-or-orphaned session, as written by a tool's recorder.
// The CLI consumes only these records — never transcripts or native stores.
type Record struct {
	SessionID  string `json:"sessionId"`
	Name       string `json:"name"`
	Cwd        string `json:"cwd"`
	Transcript string `json:"transcript"`
	PID        int    `json:"pid"`
	BootID     string `json:"bootId"`
	UpdatedAt  int64  `json:"updatedAt"`
	Tool       string `json:"tool"`
}

// live reports whether the owning process is still running in the current boot.
// Anything that is not live is an orphan: a prior-boot survivor, or a process
// that died this boot without firing its shutdown hook.
func (r Record) live(currentBoot string) bool {
	return r.BootID != "" && r.BootID == currentBoot && pidAlive(r.PID)
}

func (r Record) status(currentBoot string) string {
	if r.live(currentBoot) {
		return "live"
	}
	return "orphaned"
}

func stateRoot() string {
	if base := os.Getenv("XDG_STATE_HOME"); base != "" {
		return filepath.Join(base, "session-recovery")
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return filepath.Join(".local", "state", "session-recovery")
	}
	return filepath.Join(home, ".local", "state", "session-recovery")
}

// loadRecords reads every record from every tool subdir, dropping malformed
// files and keeping only the newest record per (bootId, pid) lineage.
func loadRecords() ([]Record, error) {
	root := stateRoot()
	var records []Record
	for _, tool := range tools {
		dir := filepath.Join(root, tool)
		entries, err := os.ReadDir(dir)
		if err != nil {
			if errors.Is(err, os.ErrNotExist) {
				continue
			}
			return nil, err
		}
		for _, entry := range entries {
			if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".json") {
				continue
			}
			data, err := os.ReadFile(filepath.Join(dir, entry.Name()))
			if err != nil {
				continue
			}
			var rec Record
			if err := json.Unmarshal(data, &rec); err != nil || rec.SessionID == "" {
				continue
			}
			if rec.Tool == "" {
				rec.Tool = tool
			}
			records = append(records, rec)
		}
	}
	return dedupeLineage(records), nil
}

// dedupeLineage keeps the newest record per (bootId, pid); a single process
// owns at most one live session, so an older sibling is a stale leftover.
func dedupeLineage(records []Record) []Record {
	type key struct {
		boot string
		pid  int
	}
	newest := make(map[key]Record, len(records))
	for _, rec := range records {
		k := key{rec.BootID, rec.PID}
		if cur, ok := newest[k]; !ok || rec.UpdatedAt > cur.UpdatedAt {
			newest[k] = rec
		}
	}
	out := make([]Record, 0, len(newest))
	for _, rec := range newest {
		out = append(out, rec)
	}
	sortByRecency(out)
	return out
}

func sortByRecency(records []Record) {
	sort.SliceStable(records, func(i, j int) bool {
		return records[i].UpdatedAt > records[j].UpdatedAt
	})
}

func sameDir(a, b string) bool {
	if a == "" || b == "" {
		return false
	}
	return resolveDir(a) == resolveDir(b)
}

func resolveDir(path string) string {
	if resolved, err := filepath.EvalSymlinks(path); err == nil {
		return filepath.Clean(resolved)
	}
	return filepath.Clean(path)
}

// scopedOrphans returns orphaned records eligible for resume. When all is
// false, only records whose cwd matches the working directory are kept.
func scopedOrphans(records []Record, currentBoot, cwd string, all bool) []Record {
	out := make([]Record, 0, len(records))
	for _, rec := range records {
		if rec.live(currentBoot) {
			continue
		}
		if !all && !sameDir(rec.Cwd, cwd) {
			continue
		}
		out = append(out, rec)
	}
	return out
}

// resolve picks the orphaned record matching arg, in order: exact session id,
// unique session-id prefix, then unique name. It errors on ambiguity.
func resolve(candidates []Record, arg string) (Record, error) {
	for _, rec := range candidates {
		if rec.SessionID == arg {
			return rec, nil
		}
	}
	if rec, err := uniqueMatch(candidates, func(r Record) bool {
		return strings.HasPrefix(r.SessionID, arg)
	}); err == nil {
		return rec, nil
	} else if !errors.Is(err, errNoMatch) {
		return Record{}, err
	}
	return uniqueMatch(candidates, func(r Record) bool {
		return r.Name != "" && r.Name == arg
	})
}

var (
	errNoMatch   = errors.New("no matching session")
	errAmbiguous = errors.New("ambiguous session")
)

func uniqueMatch(candidates []Record, pred func(Record) bool) (Record, error) {
	var matches []Record
	for _, rec := range candidates {
		if pred(rec) {
			matches = append(matches, rec)
		}
	}
	switch len(matches) {
	case 0:
		return Record{}, errNoMatch
	case 1:
		return matches[0], nil
	default:
		return Record{}, errAmbiguous
	}
}

// resumeArgv is the command that brings a session back, per owning tool.
func resumeArgv(rec Record) ([]string, error) {
	switch rec.Tool {
	case "pi":
		return []string{"pi", "--session", rec.SessionID}, nil
	case "claude":
		return []string{"claude", "--resume", rec.SessionID}, nil
	default:
		return nil, errors.New("unknown tool: " + rec.Tool)
	}
}

func pidAlive(pid int) bool {
	if pid <= 0 {
		return false
	}
	err := syscall.Kill(pid, 0)
	if err == nil {
		return true
	}
	return errors.Is(err, syscall.EPERM)
}

var execLookPath = exec.LookPath

func currentBoot() string {
	if runtime.GOOS == "darwin" {
		if out, err := exec.Command("sysctl", "-n", "kern.bootsessionuuid").Output(); err == nil {
			return strings.TrimSpace(string(out))
		}
		return ""
	}
	if data, err := os.ReadFile("/proc/sys/kernel/random/boot_id"); err == nil {
		return strings.TrimSpace(string(data))
	}
	return ""
}
