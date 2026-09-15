# Demonstrates an Array grid -- a "{...}" transform's own dep can point
# at any node, Array included -- a fixed 7 (days) x 4 (time slots)
# weekly study schedule, one cell of plain text per slot, plus a summary
# that reads the whole grid back. Each transform's own "#" comment is
# its `fatass modify` prompt (`fatass touch -p study_planner.sig -m`
# reads it and fills the transform in right after creating it).
#
# Usage: fatass touch -p study_planner.sig      # scaffold only
#        fatass touch -p study_planner.sig -m   # scaffold + fill in

StudyPlanner<Node>(
    Topics<Chat prompt:str="Brainstorm the topics this study plan needs to cover and roughly how much time each deserves. Nothing here is final.">,
    Schedule<ArrayMd dim=7x4>{
        # Read study_planner.topics' session artifacts. For each of the
        # 7 days x 4 time-slots (Schedule.write([day, slot], ...)),
        # write a short study-session plan -- what topic, and what to
        # actually do (read/practice/review) -- leaving a slot's file
        # empty ("") if that slot is a deliberate break.
        build(Topics);
    },
    WeeklySummary<SingleMd>{
        # Read every cell of study_planner.schedule. Write a short
        # weekly summary: total study hours, topic coverage balance, and
        # any days that look overloaded. Use WeeklySummary.write(...).
        build(Schedule);
    }
)
