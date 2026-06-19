package cmd

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
)

type config struct {
	IgnoredDirectories []string `json:"ignoredDirectories"`
}

func loadConfig() config {
	data, err := os.ReadFile(configPath())
	if err != nil {
		return config{}
	}
	var cfg config
	if err := json.Unmarshal(data, &cfg); err != nil {
		return config{}
	}
	return cfg
}

func saveConfig(cfg config) error {
	path := configPath()
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return err
	}
	data, err := json.MarshalIndent(cfg, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(data, '\n'), 0o600)
}

func configPath() string {
	if base := os.Getenv("XDG_CONFIG_HOME"); base != "" {
		return filepath.Join(base, "session-recovery", "config.json")
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return filepath.Join(".config", "session-recovery", "config.json")
	}
	return filepath.Join(home, ".config", "session-recovery", "config.json")
}

func (cfg config) tracks(cwd string) bool {
	for _, ignored := range cfg.IgnoredDirectories {
		if sameOrChildDir(cwd, ignored) {
			return false
		}
	}
	return true
}

func (cfg config) hasIgnoredDir(dir string) bool {
	dir = normalizeConfigDir(dir)
	for _, ignored := range cfg.IgnoredDirectories {
		if normalizeConfigDir(ignored) == dir {
			return true
		}
	}
	return false
}

func (cfg config) withoutIgnoredDir(dir string) config {
	dir = normalizeConfigDir(dir)
	kept := make([]string, 0, len(cfg.IgnoredDirectories))
	for _, ignored := range cfg.IgnoredDirectories {
		if normalizeConfigDir(ignored) != dir {
			kept = append(kept, ignored)
		}
	}
	cfg.IgnoredDirectories = kept
	return cfg
}

func sameOrChildDir(path, dir string) bool {
	path = normalizeConfigDir(path)
	dir = normalizeConfigDir(dir)
	if path == "" || dir == "" {
		return false
	}
	if path == dir {
		return true
	}
	rel, err := filepath.Rel(dir, path)
	return err == nil && rel != "." && rel != ".." && !strings.HasPrefix(rel, ".."+string(os.PathSeparator))
}

func normalizeConfigDir(path string) string {
	if path == "" {
		return ""
	}
	if path == "~" || strings.HasPrefix(path, "~/") {
		if home, err := os.UserHomeDir(); err == nil {
			path = filepath.Join(home, strings.TrimPrefix(strings.TrimPrefix(path, "~"), "/"))
		}
	}
	if !filepath.IsAbs(path) {
		if abs, err := filepath.Abs(path); err == nil {
			path = abs
		}
	}
	return resolveDir(path)
}
