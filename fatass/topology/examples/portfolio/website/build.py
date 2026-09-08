import fatass
from fatass.topology.examples.portfolio.profile import Profile as Profile
from fatass.topology.examples.portfolio.projects import Projects as Projects

def build(profile: Profile, projects: Projects, prompt: str = ""):
    print("Starting website build")
    fatass.free(
        silent=True,
        permission_mode="bypassPermissions",
        model="sonnet",
        tools="Read,Write,Edit,Glob,Grep",
        readable=[profile, projects],
        prompt=(
            "Build a personal website.\n\n"
            "Dependencies:\n"
            "- profile (node `portfolio.profile`): read everything in its readable "
            "directory for the person's bio, background, and any other personal "
            "details to feature on the site.\n"
            "- projects (node `portfolio.projects`): read everything in its readable "
            "directory for the projects to showcase on the site.\n\n"
            "Additional instructions for the site's content, style, and structure:\n"
            f"{prompt}\n\n"
            "Write the finished website (HTML/CSS/JS and any other needed files) "
            "directly into your writable directory. Choose file names and structure "
            "appropriate for a static personal website."
        ),
    )
    print("Website build complete")
