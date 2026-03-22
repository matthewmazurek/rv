complete -c rv -e

complete -c rv -n __fish_use_subcommand -a init   -d 'Create a new R project'
complete -c rv -n __fish_use_subcommand -a add    -d 'Add packages to the project'
complete -c rv -n __fish_use_subcommand -a rm     -d 'Remove packages from the project'
complete -c rv -n __fish_use_subcommand -a list   -d 'List declared packages'
complete -c rv -n __fish_use_subcommand -a update -d 'Update packages to latest versions'
complete -c rv -n __fish_use_subcommand -a sync   -d 'Install all listed packages'
complete -c rv -n __fish_use_subcommand -a run    -d 'Run an R script'
complete -c rv -n __fish_use_subcommand -a clean  -d 'Remove generated outputs'

complete -c rv -n '__fish_seen_subcommand_from init' -l no-git  -d 'Skip git init'
complete -c rv -n '__fish_seen_subcommand_from init' -l no-renv -d 'Skip renv setup'
complete -c rv -n '__fish_seen_subcommand_from init' -l rproj   -d 'Create .Rproj file'
complete -c rv -n '__fish_seen_subcommand_from init' -l slurm   -d 'Include SLURM template'
complete -c rv -n '__fish_seen_subcommand_from init' -l force   -d 'Allow non-empty directory'
complete -c rv -n '__fish_seen_subcommand_from init' -l no-sync -d 'Skip initial package sync'

complete -c rv -n '__fish_seen_subcommand_from add' -l bioc -d 'Install from Bioconductor'

complete -c rv -n '__fish_seen_subcommand_from run' -F -d 'R script'

complete -c rv -n '__fish_seen_subcommand_from clean' -l renv -d 'Also clean renv library cache'
