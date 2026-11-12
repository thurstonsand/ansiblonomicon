# Google Cloud

`terraform/google/` holds every Google Cloud project I keep, one file per project: `cloudflare` (the Access SSO OAuth client), `gemini` (the AI Studio project and its Gemini auth key), `inbox_zero` (Inbox Zero's OAuth client and its Gmail push topic), `nest` (the Device Access project's OAuth client and its `nest-events` topic), and `maps` (Maps Essentials and its restricted API key for `executor/travel/`). It authenticates with my user's application default credentials from `gcloud auth login --update-adc`. The Device Access Console, OAuth consent screens, and OAuth clients have no usable API, so they stay manual.

```sh
mise run google:plan       # google:init and google:apply for init and apply
```
