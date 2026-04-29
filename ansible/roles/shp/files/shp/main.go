// Package main implements the shp command.
package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"text/tabwriter"
	"time"

	"github.com/spf13/cobra"
)

type session struct {
	Name                     string `json:"name"`
	StartedAtUnixMS          int64  `json:"started_at_unix_ms"`
	LastConnectedAtUnixMS    *int64 `json:"last_connected_at_unix_ms"`
	LastDisconnectedAtUnixMS *int64 `json:"last_disconnected_at_unix_ms"`
	Status                   string `json:"status"`
}

type listReply struct {
	Sessions []session `json:"sessions"`
}

type app struct {
	listSessions bool
	force        bool
	dir          string
	command      string
}

func main() {
	application := &app{}
	cmd := &cobra.Command{
		Use:   "shp [-l] [--dir DIR] [--cmd COMMAND] <host> [session]",
		Short: "Attach to shpool sessions over SSH",
		Long:  "Attach to named shpool sessions over SSH. Without a session name, reuse the most recently disconnected tmp-* session or create a new temporary session.",
		Args:  application.validateArgs,
		RunE:  application.run,
		ValidArgsFunction: func(cmd *cobra.Command, args []string, toComplete string) ([]string, cobra.ShellCompDirective) {
			switch len(args) {
			case 0:
				return completeHosts(cmd.Context(), toComplete), cobra.ShellCompDirectiveNoFileComp
			case 1:
				return completeSessions(cmd.Context(), args[0], toComplete), cobra.ShellCompDirectiveNoFileComp
			default:
				return nil, cobra.ShellCompDirectiveNoFileComp
			}
		},
	}

	cmd.Flags().BoolVarP(&application.listSessions, "list", "l", false, "list remote shpool sessions")
	cmd.Flags().BoolVarP(&application.force, "force", "f", false, "detach any existing client before attaching")
	cmd.Flags().StringVarP(&application.dir, "dir", "d", "", "remote working directory for newly created sessions")
	cmd.Flags().StringVarP(&application.command, "cmd", "c", "", "remote command for newly created sessions")

	ctx := context.Background()
	cmd.SetContext(ctx)
	if err := cmd.ExecuteContext(ctx); err != nil {
		os.Exit(1)
	}
}

func (a *app) validateArgs(_ *cobra.Command, args []string) error {
	if a.listSessions {
		if len(args) != 1 {
			return errors.New("-l requires exactly one host")
		}
		if a.force || a.dir != "" || a.command != "" {
			return errors.New("-l cannot be combined with attach options")
		}
		return nil
	}
	if len(args) < 1 || len(args) > 2 {
		return errors.New("requires <host> [session]")
	}
	return nil
}

func (a *app) run(cmd *cobra.Command, args []string) error {
	host := args[0]
	if a.listSessions {
		sessions, err := remoteSessions(cmd.Context(), host, false)
		if err != nil {
			return err
		}
		return printSessionTable(os.Stdout, sessions)
	}

	var sessionName string
	if len(args) == 2 {
		sessionName = args[1]
	} else {
		chosen, err := chooseTemporarySession(cmd.Context(), host)
		if err != nil {
			return err
		}
		sessionName = chosen
	}

	remoteArgs := []string{"shpool", "attach"}
	if a.force {
		remoteArgs = append(remoteArgs, "--force")
	}
	if a.dir != "" {
		remoteArgs = append(remoteArgs, "--dir", a.dir)
	}
	if a.command != "" {
		remoteArgs = append(remoteArgs, "--cmd", a.command)
	}
	remoteArgs = append(remoteArgs, sessionName)

	return runInteractive(cmd.Context(), "ssh", "-t", host, shellCommand(remoteArgs))
}

func chooseTemporarySession(ctx context.Context, host string) (string, error) {
	sessions, err := remoteSessions(ctx, host, false)
	if err != nil {
		return "", err
	}

	disconnected := make([]session, 0)
	for _, current := range sessions {
		if strings.HasPrefix(current.Name, "tmp-") && current.Status == "Disconnected" {
			disconnected = append(disconnected, current)
		}
	}

	if len(disconnected) > 0 {
		sort.Slice(disconnected, func(i, j int) bool {
			return disconnectedAt(disconnected[i]) > disconnectedAt(disconnected[j])
		})
		return disconnected[0].Name, nil
	}

	suffix, err := randomHex(4)
	if err != nil {
		return "", err
	}
	return "tmp-" + suffix, nil
}

func disconnectedAt(current session) int64 {
	if current.LastDisconnectedAtUnixMS == nil {
		return 0
	}
	return *current.LastDisconnectedAtUnixMS
}

func remoteSessions(ctx context.Context, host string, completionMode bool) ([]session, error) {
	args := []string{}
	if completionMode {
		args = append(args, "-o", "BatchMode=yes", "-o", "ConnectTimeout=1")
	}
	args = append(args, host, "shpool", "list", "--json")

	cmd := exec.CommandContext(ctx, "ssh", args...)
	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("list remote shpool sessions: %w", err)
	}

	var reply listReply
	if err := json.Unmarshal(output, &reply); err != nil {
		return nil, fmt.Errorf("parse shpool list: %w", err)
	}
	return reply.Sessions, nil
}

func completeSessions(ctx context.Context, host string, toComplete string) []string {
	sessions, err := remoteSessions(ctx, host, true)
	if err != nil {
		return nil
	}

	matches := make([]string, 0, len(sessions))
	for _, current := range sessions {
		if strings.HasPrefix(current.Name, toComplete) {
			matches = append(matches, current.Name+"\t"+sessionDescription(current))
		}
	}
	sort.Strings(matches)
	return matches
}

func printSessionTable(writer io.Writer, sessions []session) error {
	sort.Slice(sessions, func(i, j int) bool {
		return sessions[i].Name < sessions[j].Name
	})

	table := tabwriter.NewWriter(writer, 0, 0, 2, ' ', 0)
	if _, err := fmt.Fprintln(table, "NAME\tSTARTED_AT\tSTATUS"); err != nil {
		return err
	}
	for _, current := range sessions {
		if _, err := fmt.Fprintf(table, "%s\t%s\t%s\n", current.Name, startedAt(current), normalizedStatus(current)); err != nil {
			return err
		}
	}
	return table.Flush()
}

func sessionDescription(current session) string {
	return startedAt(current) + "  " + normalizedStatus(current)
}

func startedAt(current session) string {
	return time.UnixMilli(current.StartedAtUnixMS).UTC().Format("2006-01-02T15:04:05.000Z07:00")
}

func normalizedStatus(current session) string {
	return strings.ToLower(current.Status)
}

func completeHosts(ctx context.Context, toComplete string) []string {
	hosts := make(map[string]struct{})
	for _, path := range sshConfigPaths() {
		collectHosts(path, hosts)
	}

	candidates := make([]string, 0, len(hosts))
	for host := range hosts {
		if strings.HasPrefix(host, toComplete) {
			candidates = append(candidates, host)
		}
	}

	matches := shpoolHosts(ctx, candidates)
	sort.Strings(matches)
	return matches
}

func shpoolHosts(ctx context.Context, candidates []string) []string {
	matches := make([]string, 0, len(candidates))
	var mu sync.Mutex
	var wg sync.WaitGroup

	for _, host := range candidates {
		wg.Go(func() {
			if !remoteHasShpool(ctx, host) {
				return
			}
			mu.Lock()
			matches = append(matches, host)
			mu.Unlock()
		})
	}

	wg.Wait()
	return matches
}

func remoteHasShpool(ctx context.Context, host string) bool {
	ctx, cancel := context.WithTimeout(ctx, 1500*time.Millisecond)
	defer cancel()

	cmd := exec.CommandContext(
		ctx,
		"ssh",
		"-o", "BatchMode=yes",
		"-o", "ConnectTimeout=1",
		host,
		"command", "-v", "shpool",
	)
	return cmd.Run() == nil
}

func sshConfigPaths() []string {
	home, err := os.UserHomeDir()
	if err != nil {
		return nil
	}
	return []string{filepath.Join(home, ".ssh", "config")}
}

func collectHosts(path string, hosts map[string]struct{}) {
	file, err := os.Open(path)
	if err != nil {
		return
	}
	defer func() {
		_ = file.Close()
	}()

	data, err := io.ReadAll(file)
	if err != nil {
		return
	}

	baseDir := filepath.Dir(path)
	for rawLine := range strings.SplitSeq(string(data), "\n") {
		line := strings.TrimSpace(rawLine)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}

		fields := strings.Fields(line)
		if len(fields) < 2 {
			continue
		}

		switch strings.ToLower(fields[0]) {
		case "host":
			for _, host := range fields[1:] {
				if isCompletableHost(host) {
					hosts[host] = struct{}{}
				}
			}
		case "include":
			for _, pattern := range fields[1:] {
				for _, includePath := range expandSSHInclude(baseDir, pattern) {
					collectHosts(includePath, hosts)
				}
			}
		}
	}
}

func expandSSHInclude(baseDir string, pattern string) []string {
	if strings.HasPrefix(pattern, "~") {
		home, err := os.UserHomeDir()
		if err != nil {
			return nil
		}
		pattern = filepath.Join(home, strings.TrimPrefix(pattern, "~"))
	} else if !filepath.IsAbs(pattern) {
		pattern = filepath.Join(baseDir, pattern)
	}

	matches, err := filepath.Glob(pattern)
	if err != nil {
		return nil
	}
	return matches
}

func isCompletableHost(host string) bool {
	if host == "*" || strings.HasPrefix(host, "!") {
		return false
	}
	return !strings.ContainsAny(host, "*?%")
}

func randomHex(bytes int) (string, error) {
	buf := make([]byte, bytes)
	if _, err := rand.Read(buf); err != nil {
		return "", err
	}
	return hex.EncodeToString(buf), nil
}

func shellCommand(args []string) string {
	quoted := make([]string, 0, len(args))
	for _, arg := range args {
		quoted = append(quoted, shellQuote(arg))
	}
	return strings.Join(quoted, " ")
}

func shellQuote(arg string) string {
	if arg == "" {
		return "''"
	}
	return "'" + strings.ReplaceAll(arg, "'", "'\\''") + "'"
}

func runInteractive(ctx context.Context, name string, args ...string) error {
	cmd := exec.CommandContext(ctx, name, args...)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}
