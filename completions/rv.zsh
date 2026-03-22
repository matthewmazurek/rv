#compdef rv

_rv() {
    local -a commands
    commands=(
        'init:Create a new R project'
        'add:Add packages to the project'
        'rm:Remove packages from the project'
        'list:List declared packages'
        'update:Update packages to latest versions'
        'sync:Install all listed packages'
        'run:Run an R script'
        'clean:Remove generated outputs'
    )

    _arguments -C \
        '--version[Show version]' \
        '--help[Show help]' \
        '1:command:->command' \
        '*::arg:->args'

    case "$state" in
        command)
            _describe -t commands 'rv command' commands
            ;;
        args)
            case "${words[1]}" in
                init)
                    _arguments \
                        '1:name:_files -/' \
                        '--no-git[Skip git init]' \
                        '--no-renv[Skip renv setup]' \
                        '--rproj[Create .Rproj file]' \
                        '--slurm[Include SLURM template]' \
                        '--force[Allow non-empty directory]' \
                        '--no-sync[Skip initial package sync]'
                    ;;
                add)
                    _arguments \
                        '--bioc[Install from Bioconductor]' \
                        '*:package:'
                    ;;
                rm)
                    _arguments '*:package:'
                    ;;
                update)
                    _arguments '*:package:'
                    ;;
                run)
                    _arguments \
                        '1:script:_files -g "*.R"' \
                        '*:extra:'
                    ;;
                clean)
                    _arguments '--renv[Also clean renv library cache]'
                    ;;
            esac
            ;;
    esac
}

_rv "$@"
