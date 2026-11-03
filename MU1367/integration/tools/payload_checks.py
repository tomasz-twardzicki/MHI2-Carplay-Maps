"""Generate preflight checks for the MU1367 CarPlay patch dependencies only."""
import hashlib


CHECKER_ROOTS = (
    'carplay_mu1367_guidance_v3',
    'carplay_mu1367_map_only',
    'carplay_mu1367_refinements',
)


def write_payload_checks(custom):
    # Other Custom folders belong to independent Toolbox functions. Users may
    # remove their examples or supply their own files without changing CarPlay.
    roots = sorted(p for p in custom.iterdir() if p.is_dir() and (
        p.name in ('carplay_maps_vc', 'carplay_mu1367') or
        p.name.startswith('carplay_mu1367_')))
    checks = []
    for root in roots:
        for file in sorted(root.rglob('*')):
            if file.is_file() and file.name != 'payload-check.sh':
                digest = hashlib.sha256(file.read_bytes()).hexdigest()
                checks.append('"$P/verify" "$CUSTOM_CHECK/' +
                              file.relative_to(custom).as_posix() + '" ' +
                              digest + ' || return 1')
    body = 'CUSTOM_CHECK=${P%/*}\n' + '\n'.join(checks) + '\n'
    for name in CHECKER_ROOTS:
        (custom / name / 'payload-check.sh').write_text(body)
