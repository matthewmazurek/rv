{{RENV_BLOCK}}
required_pkgs <- c(
  "yaml"
)

missing_pkgs <- required_pkgs[!vapply(required_pkgs, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing_pkgs) > 0) {
  install.packages(missing_pkgs)
}

# Add project-specific packages here, for example:
# install.packages(c("dplyr", "ggplot2", "data.table"))
# if (!requireNamespace("BiocManager", quietly = TRUE)) install.packages("BiocManager")
# BiocManager::install(c("SingleCellExperiment"))

{{RENV_SNAPSHOT}}

message("Environment setup complete.")
