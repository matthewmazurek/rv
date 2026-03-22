suppressPackageStartupMessages({
  if (file.exists("renv/activate.R")) source("renv/activate.R")
  source("R/utils.R")
})

args <- parse_args()
cfg  <- load_config(args$config)

ensure_dir("results")
ensure_dir("logs")

set.seed(cfg$seed %||% 123)

workers <- cfg$future_workers %||% 1

message_block("Starting analysis")
message("Working directory: ", getwd())
message("Project root: ", get_project_root())
message("Input: ", args$input %||% "<none>")
message("Output: ", args$output %||% "results/output.txt")

# ------------------------------------------------------------------
# TEMPLATE SECTION
# Replace this with your actual workflow.
# ------------------------------------------------------------------

output_path <- args$output %||% "results/output.txt"

lines <- c(
  paste("Timestamp:", Sys.time()),
  paste("Project:", cfg$project_name %||% "unknown"),
  paste("Working directory:", getwd()),
  paste("Input:", args$input %||% "<none>")
)

writeLines(lines, con = output_path)

message("Wrote output to: ", output_path)
message_block("Analysis complete")
