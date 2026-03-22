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
  args <- commandArgs(trailingOnly = TRUE)

  out <- list(
    input = NULL,
    output = NULL,
    config = "config/analysis.yaml"
  )

  if (length(args) == 0) {
    return(out)
  }

  i <- 1L
  while (i <= length(args)) {
    key <- args[[i]]

    if (key %in% c("--input", "--output", "--config")) {
      if (i == length(args)) {
        stop("Missing value for argument: ", key)
      }
      value <- args[[i + 1L]]
      nm <- substring(key, 3L)
      out[[nm]] <- value
      i <- i + 2L
    } else {
      stop("Unknown argument: ", key)
    }
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
