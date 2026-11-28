# Google Cloud

`terraform/google/` holds every Google Cloud project I keep, one file per project: `cloudflare` (the Access SSO and Comail OAuth clients), `gemini` (the AI Studio project, its Gemini auth key, and the Colab API for [Executor](../../executor/google-colab/)), `nest` (the Device Access project's OAuth client and its `nest-events` topic), and `maps` (Maps Essentials and its restricted API key for `executor/travel/`). The standalone `colab` project remains managed pending retirement. The stack uses my user's application default credentials from `gcloud auth login --update-adc`. The Device Access Console, OAuth consent screens, and OAuth clients have no usable API, so they stay manual.

```sh
mise run google:plan       # google:init and google:apply for init and apply
```

The Colab API enablement also enables Google's hosted Colab MCP. In the Gemini project's [Google Auth Platform](https://console.cloud.google.com/auth/clients?project=gen-lang-client-0166268742), set up consent for the Colab scope and create a **Web application** client marked **Use this client for an AI-powered agent**, with `https://executor.sh/api/oauth/callback` as an authorized redirect URI. Enter the OAuth client secret only in Executor's connection form, not in Terraform.
