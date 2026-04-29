#!/usr/bin/env nu

# Generate profile stats from GitHub API via gh CLI.
# Outputs a JSON blob that can be injected into profile/index.html.

def main [] {
    let repos = (gh api users/89jobrien/repos --paginate
        | from json
        | where fork == false)

    let repo_count = ($repos | length)

    # Language breakdown by repo count
    let lang_counts = ($repos
        | where language != null
        | get language
        | uniq --count
        | sort-by count --reverse)

    let top_langs = ($lang_counts | first 5)

    # Repos active in last 30 days
    let cutoff = ((date now) - 30day)
    let active_repos = ($repos
        | where { |r| ($r.pushed_at | into datetime) > $cutoff }
        | length)

    # Most recent push
    let most_recent = ($repos
        | sort-by pushed_at --reverse
        | first
        | get name)

    # LOC: fetch language bytes for every repo and sum
    let all_lang_bytes = ($repos | each { |r|
        let langs = (gh api $"repos/89jobrien/($r.name)/languages" | from json)
        $langs
    } | reduce { |it, acc| $it | merge $acc })

    # Actually we need to sum per-language across repos properly
    let lang_totals = ($repos | each { |r|
        gh api $"repos/89jobrien/($r.name)/languages" | from json
    } | each { |row|
        $row | transpose key value
    } | flatten | group-by key | transpose key value | each { |g|
        { lang: $g.key, bytes: ($g.value | each { |v| $v.value } | math sum) }
    } | sort-by bytes --reverse)

    let total_bytes = ($lang_totals | get bytes | math sum)
    # Rough LOC estimate: ~40 bytes per line for code
    let total_loc = ($total_bytes / 40 | into int)

    let rust_bytes = ($lang_totals
        | where lang == "Rust"
        | get bytes
        | first
        | default 0)
    let rust_loc = ($rust_bytes / 40 | into int)

    let stats = {
        repo_count: $repo_count
        active_repos_30d: $active_repos
        most_recent_push: $most_recent
        top_languages: ($top_langs | each { |l| { lang: $l.value, repos: $l.count } })
        total_bytes: $total_bytes
        total_loc_approx: $total_loc
        rust_loc_approx: $rust_loc
        lang_breakdown: ($lang_totals | first 5 | each { |l|
            { lang: $l.lang, loc: ($l.bytes / 40 | into int) }
        })
        generated_at: (date now | format date "%Y-%m-%d %H:%M UTC")
    }

    $stats | to json
}
