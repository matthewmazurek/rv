_rv() {
    local cur prev commands
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    commands="init add rm list update sync run clean"

    if [[ ${COMP_CWORD} -eq 1 ]]; then
        COMPREPLY=($(compgen -W "${commands} --version --help" -- "${cur}"))
        return
    fi

    case "${COMP_WORDS[1]}" in
        init)
            COMPREPLY=($(compgen -W "--no-git --no-renv --rproj --slurm --force --no-sync" -- "${cur}"))
            ;;
        add)
            COMPREPLY=($(compgen -W "--bioc" -- "${cur}"))
            ;;
        clean)
            COMPREPLY=($(compgen -W "--renv" -- "${cur}"))
            ;;
        run)
            if [[ "${cur}" == -* ]]; then
                return
            fi
            COMPREPLY=($(compgen -f -X '!*.R' -- "${cur}"))
            ;;
    esac
}

complete -F _rv rv
