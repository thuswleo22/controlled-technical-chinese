"""Reproduce revision-pinned snapshots of Chinese engineering prose."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import hashlib
import json
from pathlib import Path
import re
from subprocess import check_output

ROOT = Path(__file__).resolve().parents[1]
REVISION = "47132eb5367cfdcba0a3b33a0b3ffc81185bd7e8"
FILES = {
    "API": ("reference/using-api/api-concepts.md", "concepts/overview/kubernetes-api.md"),
    "架构": ("concepts/architecture/_index.md", "concepts/architecture/nodes.md"),
    "操作": (
        "tasks/administer-cluster/safely-drain-node.md",
        "tasks/debug/debug-application/debug-pods.md",
    ),
    "安全": (
        "concepts/security/pod-security-admission.md",
        "tasks/administer-cluster/securing-a-cluster.md",
    ),
}


MDN_REVISION = "69242ec9d69118cdfeee571ac44c5325530bfdbc"
MDN_FILES = {
    "API": ("web/api/fetch_api/index.md",),
    "架构": ("web/http/guides/fetch_metadata/index.md",),
    "操作": ("web/api/fetch_api/using_fetch/index.md",),
    "安全": ("web/http/reference/headers/content-security-policy/index.md",),
}


KUBERNETES_LEXICON_FILES = {
    "存储": ("tasks/administer-cluster/change-pv-reclaim-policy.md",
             "tasks/administer-cluster/encrypt-data.md"),
    "网络": ("concepts/services-networking/service.md", "concepts/services-networking/network-policies.md"),
    "权限": ("reference/access-authn-authz/authentication.md", "reference/access-authn-authz/rbac.md"),
    "运维": ("tasks/configure-pod-container/configure-liveness-readiness-startup-probes.md",
             "concepts/workloads/controllers/deployment.md",
             "concepts/scheduling-eviction/pod-priority-preemption.md"),
}


TIDB_REVISION = "5214a56c3ea96fde99fe3bea0f0c55b02d277757"
TIDB_FILES = {
    "存储": ("br/backup-and-restore-design.md", "br/br-snapshot-manual.md",
             "br/br-pitr-manual.md", "dumpling-overview.md",
             "tidb-lightning/data-import-best-practices.md", "choose-index.md", "statistics.md"),
    "权限": ("privilege-management.md", "user-account-management.md", "password-management.md",
             "generate-self-signed-certificates.md", "enable-tls-between-clients-and-servers.md"),
    "运维": ("scale-tidb-using-tiup.md", "tiproxy/tiproxy-load-balance.md",
             "tidb-resource-control-runaway-queries.md", "tiup/tiup-component-cluster-scale-in.md"),
}


def collect(job, repo, revision, prefix, include_lists=False):
    genre, name, split = job
    path = prefix + name
    url = f"https://raw.githubusercontent.com/{repo}/{revision}/{path}"
    raw = check_output(["curl", "-fsSL", "--retry", "3", "--max-time", "20", url])
    snapshot = raw.decode()
    # Preserve line numbering while removing translated source comments and code.
    snapshot = re.sub(r"<!--.*?-->|^---\n.*?\n---", lambda m: "\n" * m[0].count("\n"),
                      snapshot, flags=re.S)
    paragraphs = []
    block = []
    in_fence = False
    for line_number, line in enumerate(snapshot.splitlines() + [""], 1):
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
        if include_lists and re.match(r"^\s*(?:[-*+] |[0-9]+\. )", line):
            line = re.sub(r"^\s*(?:[-*+] |[0-9]+\. )", "", line, count=1)
        prose = (not in_fence and line and not line.startswith((" ", "\t", "#", "|", "{", "<", ">",
                                                                  "-", "*", "```", "~~~"))
                 and re.search(r"[\u3400-\u9fff]", line))
        if prose:
            block.append((line_number, line))
            continue
        if block:
            text = " ".join(value for _, value in block)
            text = re.sub(r"!?\[([^\]]+)\]\([^)]+\)", r"\1", text)
            paragraphs.append({"line": block[0][0], "text": text})
            block.clear()
    if not paragraphs:
        raise ValueError(f"No prose found at {url}")
    return {
        "genre": genre, "path": path, "source": url, "sha256": hashlib.sha256(raw).hexdigest(),
        "split": split,
        "paragraphs": paragraphs,
    }


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--dataset", choices=("kubernetes", "mdn", "tidb", "kubernetes-lexicon", "tidb-status"), default="kubernetes")
    args = cli.parse_args()
    if args.dataset == "kubernetes":
        repo, revision = "kubernetes/website", REVISION
        prefix, target = "content/zh-cn/docs/", "kubernetes_v134.json"
        license_source = f"https://github.com/{repo}/blob/{revision}/LICENSE"
        jobs = [(genre, name, split) for genre, names in FILES.items()
                for name, split in zip(names, ("development", "holdout"))]
    elif args.dataset == "kubernetes-lexicon":
        repo, revision = "kubernetes/website", REVISION
        prefix, target = "content/zh-cn/docs/", "kubernetes_lexicon_external.json"
        license_source = f"https://github.com/{repo}/blob/{revision}/LICENSE"
        jobs = [(genre, name, "lexicon_external")
                for genre, paths in KUBERNETES_LEXICON_FILES.items() for name in paths]
    elif args.dataset == "mdn":
        repo, revision = "mdn/translated-content", MDN_REVISION
        prefix, target = "files/zh-cn/", "mdn_external.json"
        license_source = "https://developer.mozilla.org/en-US/docs/MDN/Writing_guidelines/Attrib_copyright_license"
        jobs = [(genre, name, "external") for genre, names in MDN_FILES.items() for name in names]
    elif args.dataset == "tidb-status":
        repo, revision = "pingcap/docs-cn", TIDB_REVISION
        prefix, target = "", "tidb_status_contexts.json"
        license_source = f"https://github.com/{repo}/blob/{revision}/LICENSE"
        jobs = [("状态", name, "lexicon_status") for name in (
            "tidb-scheduling.md", "dashboard/dashboard-cluster-info.md",
            "best-practices/pd-scheduling-best-practices.md", "pd-configuration-file.md")]
    else:
        repo, revision = "pingcap/docs-cn", TIDB_REVISION
        prefix, target = "", "tidb_lexicon_external.json"
        license_source = f"https://github.com/{repo}/blob/{revision}/LICENSE"
        jobs = [(genre, name, "lexicon_external") for genre, names in TIDB_FILES.items() for name in names]
    download = partial(collect, repo=repo, revision=revision, prefix=prefix,
                       include_lists=args.dataset == "tidb-status")
    with ThreadPoolExecutor(max_workers=4) as executor:
        documents = list(executor.map(download, jobs))
    output = {
        "revision": revision,
        "license_source": license_source,
        "extraction": ("Chinese prose including list bodies, comments and code omitted and links flattened"
                       if args.dataset == "tidb-status" else
                       "Chinese prose blocks with comments and code omitted and links flattened"),
        "documents": documents,
    }
    (ROOT / "corpus" / target).write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
