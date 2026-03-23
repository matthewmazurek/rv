source("R/init.R")
# Provides: cfg
# cfg — analysis.yaml defaults merged with CLI overrides (CLI wins)

# SLURM environment — merge into cfg (CLI args > SLURM env > config defaults)
slurm_env <- list(
  job_id   = Sys.getenv("SLURM_JOB_ID", ""),
  task_id  = Sys.getenv("SLURM_ARRAY_TASK_ID", ""),
  cpus     = as.integer(Sys.getenv("SLURM_CPUS_PER_TASK", "1")),
  mem_mb   = Sys.getenv("SLURM_MEM_PER_NODE", ""),
  ntasks   = Sys.getenv("SLURM_NTASKS", "1"),
  nodelist = Sys.getenv("SLURM_NODELIST", "")
)
for (k in names(slurm_env)) {
  if (is.null(cfg[[k]]) && nzchar(as.character(slurm_env[[k]]))) {
    cfg[[k]] <- slurm_env[[k]]
  }
}

if (!is.null(cfg$seed)) set.seed(cfg$seed)

workers <- if (identical(cfg$workers, "auto")) cfg$cpus else cfg$workers %||% cfg$cpus

output_path <- cfg$output %||% "results/output.txt"

lines <- c(
  paste("Timestamp:", Sys.time()),
  paste("Project:", cfg$project_name %||% "unknown"),
  paste("Working directory:", getwd()),
  paste("Input:", cfg$input %||% "<none>"),
  paste("SLURM Job:", cfg$job_id %||% "<local>"),
  paste("Workers:", workers)
)

writeLines(lines, con = output_path)

message("Wrote output to: ", output_path)
message_block("Analysis complete")
