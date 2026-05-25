# invisible bash tab-completion.
#
# Install:
#   1. cp scripts/completions/invisible.bash ~/.invisible/completions/invisible.bash
#      (or anywhere; just source it from ~/.bashrc)
#   2. Add to ~/.bashrc:
#        source ~/.invisible/completions/invisible.bash
#   3. open a new shell.
#
# Less polished than the zsh version — bash's completion model doesn't
# support per-positional argument types as cleanly. Still completes
# project names for every command that takes one.

_invisible_projects() {
  local toml="${INVISIBLE_HOME:-$HOME/.invisible}/invisible.toml"
  [[ -f "$toml" ]] || return 1
  awk '
    /^[[:space:]]*\[\[projects\]\][[:space:]]*$/ { in_block = 1; next }
    /^[[:space:]]*\[/                            { in_block = 0 }
    in_block && /^[[:space:]]*name[[:space:]]*=/ {
      sub(/^[^=]*=[[:space:]]*"?/, "")
      sub(/"?[[:space:]]*$/, "")
      print
    }
  ' "$toml" 2>/dev/null
}

_invisible_complete_project_first_arg() {
  local cur="${COMP_WORDS[COMP_CWORD]}"
  if [[ $COMP_CWORD -eq 1 ]]; then
    local projs
    projs=$(_invisible_projects)
    COMPREPLY=( $(compgen -W "$projs" -- "$cur") )
  fi
}

_invisible_review_complete() {
  local cur="${COMP_WORDS[COMP_CWORD]}"
  local prev="${COMP_WORDS[COMP_CWORD-1]}"
  case "$prev" in
    --task|--max-iters) return 0 ;;
  esac
  if [[ $COMP_CWORD -eq 1 ]]; then
    COMPREPLY=( $(compgen -W "$(_invisible_projects)" -- "$cur") )
  else
    COMPREPLY=( $(compgen -W "--task --max-iters --continuous --resume --stop --force" -- "$cur") )
  fi
}

_invisible_ship_complete() {
  local cur="${COMP_WORDS[COMP_CWORD]}"
  if [[ $COMP_CWORD -eq 1 ]]; then
    COMPREPLY=( $(compgen -W "$(_invisible_projects)" -- "$cur") )
  else
    COMPREPLY=( $(compgen -W "--pr --merge --no-squash --base --force" -- "$cur") )
  fi
}

_invisible_main_complete() {
  local cur="${COMP_WORDS[COMP_CWORD]}"
  local prev="${COMP_WORDS[COMP_CWORD-1]}"
  if [[ "$prev" == "--project" ]]; then
    COMPREPLY=( $(compgen -W "$(_invisible_projects)" -- "$cur") )
    return 0
  fi
  COMPREPLY=( $(compgen -W "kill --project" -- "$cur") )
}

complete -F _invisible_main_complete    invisible
complete -F _invisible_review_complete  invisible-review
complete -F _invisible_ship_complete    invisible-ship
complete -F _invisible_complete_project_first_arg invisible-cleanup
complete -F _invisible_complete_project_first_arg invisible-watch
complete -F _invisible_complete_project_first_arg invisible-vps-handoff
complete -F _invisible_complete_project_first_arg invisible-history
complete -F _invisible_complete_project_first_arg invisible-new
