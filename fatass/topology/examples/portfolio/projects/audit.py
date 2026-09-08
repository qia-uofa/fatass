from .audit_info import audit_info
from .audit_summary import audit_summary
from fatass.topology.examples.portfolio.projects import Projects as Projects


def audit(projects: Projects, i: int = -1):
    print("audit: starting")
    audit_info(projects, i)
    audit_summary(projects, i)
    print("audit: done")
