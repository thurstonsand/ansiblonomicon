// Command ghostty-nav sends navigation requests to ghostty-navd.
package main

import (
	"errors"
	"fmt"
	"os"

	"github.com/spf13/cobra"

	"house.thurstons/ghostty-nav/internal/client"
	"house.thurstons/ghostty-nav/internal/osc"
	"house.thurstons/ghostty-nav/internal/protocol"
	"house.thurstons/ghostty-nav/internal/tty"
)

type options struct {
	tty  string
	wait bool
}

func main() {
	opts := &options{}
	root := &cobra.Command{
		Use:           "ghostty-nav",
		SilenceUsage:  true,
		SilenceErrors: true,
	}
	root.PersistentFlags().StringVar(&opts.tty, "tty", "", "terminal TTY path override")
	root.PersistentFlags().BoolVar(&opts.wait, "wait", false, "wait for acknowledgement for commands that normally fire and forget")

	root.AddCommand(
		pingCmd(),
		terminalIDCmd(opts),
		tabTerminalCountCmd(),
		activateCmd(opts),
		deactivateCmd(opts),
		moveCmd(opts),
		splitCmd(opts),
		resizeCmd(opts),
		toggleZoomCmd(opts),
		pasteCmd(opts),
		clearCacheCmd(opts),
		titleCmd(),
	)

	if err := root.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, "ghostty-nav:", err)
		if coded, ok := errors.AsType[exitError](err); ok {
			os.Exit(coded.code)
		}
		os.Exit(1)
	}
}

func send(req protocol.Request) (*protocol.Response, error) {
	return client.Send(client.SocketPath(), req)
}

func printValue(resp *protocol.Response) {
	if resp != nil && resp.Value != "" {
		fmt.Println(resp.Value)
	}
}

func sendRequest(req protocol.Request) error {
	_, err := send(req)
	return err
}

func sendWithTTY(opts *options, build func(string) protocol.Request) error {
	value, err := requestTTY(opts)
	if err != nil {
		return err
	}
	return sendRequest(build(value))
}

func requestTTY(opts *options) (string, error) {
	if opts.tty != "" {
		return tty.Normalize(opts.tty), nil
	}
	if value := os.Getenv("GHOSTTY_NAV_TTY"); value != "" {
		return tty.Normalize(value), nil
	}
	return tty.Current()
}

func pingCmd() *cobra.Command {
	return &cobra.Command{
		Use:  "ping",
		Args: cobra.NoArgs,
		RunE: func(_ *cobra.Command, _ []string) error {
			resp, err := send(protocol.PingRequest{Envelope: protocol.Envelope{Command: "ping", Reply: true}})
			if err != nil {
				return err
			}
			printValue(resp)
			return nil
		},
	}
}

func terminalIDCmd(opts *options) *cobra.Command {
	return &cobra.Command{
		Use:  "terminal-id",
		Args: cobra.NoArgs,
		RunE: func(_ *cobra.Command, _ []string) error {
			maybeTTY, ttyErr := requestTTY(opts)
			if ttyErr != nil {
				maybeTTY = ""
			}
			resp, err := send(protocol.TerminalIDRequest{Envelope: protocol.Envelope{Command: "terminal-id", Reply: true}, TTY: maybeTTY})
			if err != nil {
				return err
			}
			printValue(resp)
			return nil
		},
	}
}

func tabTerminalCountCmd() *cobra.Command {
	return &cobra.Command{
		Use:  "tab-terminal-count",
		Args: cobra.NoArgs,
		RunE: func(_ *cobra.Command, _ []string) error {
			resp, err := send(protocol.TabTerminalCountRequest{Envelope: protocol.Envelope{Command: "tab-terminal-count", Reply: true}})
			if err != nil {
				return err
			}
			printValue(resp)
			return nil
		},
	}
}

func activateCmd(opts *options) *cobra.Command {
	return &cobra.Command{
		Use:  "activate <table>",
		Args: cobra.ExactArgs(1),
		RunE: func(_ *cobra.Command, args []string) error {
			return sendWithTTY(opts, func(value string) protocol.Request {
				return protocol.ActivateRequest{Envelope: protocol.Envelope{Command: "activate", Reply: opts.wait}, TTY: value, Table: args[0]}
			})
		},
	}
}

func deactivateCmd(opts *options) *cobra.Command {
	return &cobra.Command{
		Use:  "deactivate",
		Args: cobra.NoArgs,
		RunE: func(_ *cobra.Command, _ []string) error {
			return sendWithTTY(opts, func(value string) protocol.Request {
				return protocol.DeactivateRequest{Envelope: protocol.Envelope{Command: "deactivate", Reply: opts.wait}, TTY: value}
			})
		},
	}
}

func moveCmd(opts *options) *cobra.Command {
	return &cobra.Command{
		Use:  "move <left|down|up|right>",
		Args: cobra.ExactArgs(1),
		RunE: func(_ *cobra.Command, args []string) error {
			return sendWithTTY(opts, func(value string) protocol.Request {
				return protocol.MoveRequest{Envelope: protocol.Envelope{Command: "move", Reply: opts.wait}, TTY: value, Direction: args[0]}
			})
		},
	}
}

func splitCmd(opts *options) *cobra.Command {
	var cwd string
	var commandText string
	var focus string
	cmd := &cobra.Command{
		Use:  "split <left|down|up|right>",
		Args: cobra.ExactArgs(1),
		RunE: func(_ *cobra.Command, args []string) error {
			return sendWithTTY(opts, func(value string) protocol.Request {
				return protocol.SplitRequest{Envelope: protocol.Envelope{Command: "split", Reply: true}, TTY: value, Direction: args[0], CWD: cwd, CommandText: commandText, Focus: focus}
			})
		},
	}
	cmd.Flags().StringVar(&cwd, "cwd", "", "initial working directory")
	cmd.Flags().StringVar(&commandText, "command", "", "command to run")
	cmd.Flags().StringVar(&focus, "focus", "new", "focus target: new or original")
	return cmd
}

func resizeCmd(opts *options) *cobra.Command {
	var pixels int
	var percent float64
	cmd := &cobra.Command{
		Use:  "resize <left|down|up|right>",
		Args: cobra.ExactArgs(1),
		RunE: func(_ *cobra.Command, args []string) error {
			value, err := requestTTY(opts)
			if err != nil {
				return err
			}
			amount := protocol.ResizeAmount{}
			switch {
			case pixels > 0 && percent == 0:
				amount.Pixels = &pixels
			case percent > 0 && pixels == 0:
				amount.Percent = &percent
			default:
				return errors.New("specify exactly one of --pixels or --percent")
			}
			return sendRequest(protocol.ResizeRequest{Envelope: protocol.Envelope{Command: "resize", Reply: true}, TTY: value, Direction: args[0], Amount: amount})
		},
	}
	cmd.Flags().IntVar(&pixels, "pixels", 0, "resize amount in pixels")
	cmd.Flags().Float64Var(&percent, "percent", 0, "resize amount as percentage")
	return cmd
}

func toggleZoomCmd(opts *options) *cobra.Command {
	return &cobra.Command{
		Use:  "toggle-zoom",
		Args: cobra.NoArgs,
		RunE: func(_ *cobra.Command, _ []string) error {
			return sendWithTTY(opts, func(value string) protocol.Request {
				return protocol.ToggleZoomRequest{Envelope: protocol.Envelope{Command: "toggle-zoom", Reply: true}, TTY: value}
			})
		},
	}
}

func pasteCmd(opts *options) *cobra.Command {
	var outputDir string
	var jsonOutput bool
	cmd := &cobra.Command{
		Use:  "paste",
		Args: cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			return runPaste(cmd.OutOrStdout(), opts, outputDir, jsonOutput)
		},
	}
	cmd.Flags().StringVar(&outputDir, "output-dir", "/tmp/pi-paste-file", "directory for materialized clipboard files")
	cmd.Flags().BoolVar(&jsonOutput, "json", false, "print structured paste metadata")
	return cmd
}

func clearCacheCmd(opts *options) *cobra.Command {
	var all bool
	cmd := &cobra.Command{
		Use:  "clear-cache",
		Args: cobra.NoArgs,
		RunE: func(_ *cobra.Command, _ []string) error {
			if all {
				return sendRequest(protocol.ClearCacheRequest{Envelope: protocol.Envelope{Command: "clear-cache", Reply: true}})
			}
			return sendWithTTY(opts, func(value string) protocol.Request {
				return protocol.ClearCacheRequest{Envelope: protocol.Envelope{Command: "clear-cache", Reply: true}, TTY: value}
			})
		},
	}
	cmd.Flags().BoolVar(&all, "all", false, "clear all cached terminal mappings")
	return cmd
}

func titleCmd() *cobra.Command {
	return &cobra.Command{
		Use:  "title <text>",
		Args: cobra.ExactArgs(1),
		RunE: func(_ *cobra.Command, args []string) error {
			return osc.Title(args[0])
		},
	}
}
