# Google Colab

Uses Google's [hosted Colab MCP](https://developers.google.com/colab/api/reference/mcp) to inspect runtime eligibility, provision CPU/GPU/TPU runtimes, and execute Python in Colab kernels. Accelerator access and usage are governed by the signed-in Colab account. Tool responses return text, not plots or binary artifacts.

Enable the [Colab API](https://console.cloud.google.com/apis/library/colaboratory.googleapis.com) and its [remote MCP server](https://docs.cloud.google.com/mcp/enable-disable-mcp-servers) in the project owning the OAuth client. Connect a Google account from the app's **Accounts** tab. If Executor asks for a client, create a Web application client marked for AI agents and copy the redirect URI shown on the form. It requests only the Colab scope; the existing Google Workspace connection is separate.

Verify the connection with `colab.get_subscription` and `colab.list_runtime_specs` before provisioning. Prefer reusing a runtime from `list_runtimes` and an explicit kernel session for related calls. Close sessions and release runtimes you created when done. Use Browser approval for provisioning, code execution and teardown. Runtime metadata omits direct-access credentials. Upstream calls are limited to five minutes, or less if the client cancels; the connector isn't a durable batch-job scheduler.
