suppressPackageStartupMessages({
  if (file.exists("renv/activate.R")) source("renv/activate.R")
  source("R/utils.R")
})

cli <- parse_args()
cfg <- load_config(cli$config %||% "config/analysis.yaml")

# CLI args override config defaults
cli$config <- NULL
cfg[names(cli)] <- cli

ensure_dir("results")
ensure_dir("logs")

message_block("Starting analysis")
message("Working directory: ", getwd())
message("Project root: ", get_project_root())
