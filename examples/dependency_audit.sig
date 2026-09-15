# Demonstrates a `Repo` node -- its own home/ directory is a real git
# repository (`fatass create` already ran `git init` there) -- alongside
# a transform that reads from it. Each transform's own "#" comment is
# its `fatass modify` prompt (`fatass touch -p dependency_audit.sig -m`
# reads it and fills the transform in right after creating it).
#
# Usage: fatass touch -p dependency_audit.sig      # scaffold only
#        fatass touch -p dependency_audit.sig -m   # scaffold + fill in

DependencyAudit<Node>(
    Vendored<Repo>,
    Report<SingleMd>{
        # dependency_audit.vendored's home/ directory is its own git
        # repo -- clone or otherwise populate it first (e.g. via
        # `fatass sh`), then read its contents here. Write a short
        # license/dependency audit: what's vendored, its license, and
        # the exact commit/tag pinned in this checkout. Use
        # Report.write(...).
        build(Vendored);
    }
)
