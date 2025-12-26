resource "cloudflare_pages_project" "nixonomicon_tesla" {
  account_id        = local.account_id
  name              = "nixonomicon-tesla"
  production_branch = "main"

  source {
    type = "github"
    config {
      owner                         = "thurstonsand"
      repo_name                     = "nixonomicon"
      production_branch             = "main"
      deployments_enabled           = true
      production_deployment_enabled = true
      pr_comments_enabled           = true
      preview_branch_includes       = ["*"]
      preview_deployment_setting    = "all"
    }
  }

  build_config {
    build_command   = "npm run build"
    destination_dir = "public"
    root_dir        = "cloudflare-pages/tesla"
  }
}

resource "cloudflare_pages_domain" "tesla" {
  account_id   = local.account_id
  project_name = cloudflare_pages_project.nixonomicon_tesla.name
  domain       = "tesla.${local.zone_name}"
}
