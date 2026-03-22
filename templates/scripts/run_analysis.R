source("R/init.R")
# Provides: cfg
# cfg — analysis.yaml defaults merged with CLI overrides (CLI wins)

if (!is.null(cfg$seed)) set.seed(cfg$seed)

output_path <- cfg$output %||% "results/output.txt"

lines <- c(
  paste("Timestamp:", Sys.time()),
  paste("Project:", cfg$project_name %||% "unknown"),
  paste("Working directory:", getwd()),
  paste("Input:", cfg$input %||% "<none>")
)

writeLines(lines, con = output_path)

message("Wrote output to: ", output_path)
message_block("Analysis complete")
