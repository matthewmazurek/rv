{{RENV_BLOCK}}
if (!requireNamespace("pak", quietly = TRUE)) install.packages("pak")

required_pkgs <- c(
  "yaml"
)

for (spec in required_pkgs) {
  parts <- strsplit(spec, "@", fixed = TRUE)[[1]]
  pkg <- parts[1]
  ver <- if (length(parts) > 1) parts[2] else NULL

  if (requireNamespace(pkg, quietly = TRUE)) {
    if (!is.null(ver) && as.character(packageVersion(pkg)) != ver) {
      message(sprintf("Updating %s to version %s", pkg, ver))
    } else {
      next
    }
  }

  if (!is.null(ver)) {
    pak::pkg_install(spec)
  } else {
    pak::pkg_install(pkg)
  }
}

{{RENV_SNAPSHOT}}

message("Environment setup complete.")
