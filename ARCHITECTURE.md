# TheySix farm exporter — Architecture

main.py loads channel IDs from the environment. On ready, it scans the configured channels, parses messages and embeds, groups assets by DN, and writes farms_builds.jsonl and missing_report.jsonl before exiting.
