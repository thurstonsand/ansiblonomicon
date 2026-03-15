declare module "@ampcode/plugin" {
  export interface PluginLogger {
    log: (...args: unknown[]) => void;
  }

  export interface PluginUI {
    notify(message: string): Promise<void>;
  }

  export interface PluginCommandContext {
    ui: PluginUI;
    thread?: {
      id: `T-${string}`;
    };
  }

  export interface PluginEventContext {
    ui: PluginUI;
  }

  export interface ShellResult {
    exitCode: number;
    stdout: string;
    stderr: string;
  }

  export type ShellFunction = (
    strings: TemplateStringsArray,
    ...values: unknown[]
  ) => Promise<ShellResult>;

  export interface Subscription {
    unsubscribe(): void;
  }

  export interface AgentStartResult {
    message?: {
      content: string;
      display: true;
    };
  }

  export interface PluginAPI {
    logger: PluginLogger;
    $: ShellFunction;

    registerCommand(
      id: string,
      options: {
        title: string;
        category?: string;
        description?: string;
      },
      handler: (ctx: PluginCommandContext) => void | Promise<void>,
    ): Subscription;

    on(
      event: "session.start",
      handler: (
        event: Record<string, never>,
        ctx: PluginEventContext,
      ) => void | Promise<void>,
    ): Subscription;

    on(
      event: "agent.start",
      handler: (
        event: {
          message: string;
          id: number;
        },
        ctx: PluginEventContext,
      ) => AgentStartResult | void | Promise<AgentStartResult | void>,
    ): Subscription;
  }
}
