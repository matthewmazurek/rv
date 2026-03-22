suppressPackageStartupMessages({
  library(yaml)
})

`%||%` <- function(x, y) if (is.null(x)) y else x

get_project_root <- function() {
  normalizePath(getwd(), winslash = "/", mustWork = TRUE)
}

load_config <- function(path = "config/analysis.yaml") {
  if (!file.exists(path)) {
    stop("Config file not found: ", path)
  }
  yaml::read_yaml(path)
}

parse_args <- function() {
  raw <- commandArgs(trailingOnly = TRUE)
  out <- list()

  if (length(raw) == 0) return(out)

  i <- 1L
  while (i <= length(raw)) {
    key <- raw[[i]]
    if (!startsWith(key, "--")) stop("Expected --flag, got: ", key)
    if (i == length(raw)) stop("Missing value for argument: ", key)
    out[[substring(key, 3L)]] <- raw[[i + 1L]]
    i <- i + 2L
  }

  out
}

ensure_dir <- function(path) {
  dir.create(path, recursive = TRUE, showWarnings = FALSE)
  invisible(path)
}

message_block <- function(...) {
  cat("\n", paste0(..., collapse = ""), "\n", sep = "")
}
