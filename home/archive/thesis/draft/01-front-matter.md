# An Ontological Perspective on LLM Beliefs

**Bachelorarbeit**

Johann Wolfgang Goethe-Universität Frankfurt am Main
Fachbereich Informatik und Mathematik
B.Sc. Informatik

Submitted by: Qi
Supervisor (First Examiner): Prof. Dr. Visvanathan Ramesh
Themenausgabe: 27 June 2026 · Abgabetermin: 31 August 2026

---

## Zusammenfassung

Große Sprachmodelle (Large Language Models, LLMs) geben auf Nachfrage
Selbstauskünfte über den eigenen Wissensstand, am häufigsten in Form einer
verbalisierten Konfidenzangabe. Kumaran et al. (2026) zeigen, dass diese
Angabe nicht erst bei der Verbalisierung berechnet wird: die relevante
Information entsteht bereits während der Antwortgenerierung, wird an der
Tokenposition unmittelbar nach der Antwort zwischengespeichert und später
abgerufen. Die vorliegende Arbeit reproduziert diesen Befund unabhängig und in
reduziertem Maßstab auf Qwen2.5-7B-Instruct und erweitert ihn anschließend über
Konfidenz hinaus. Dazu wird ein neues Paket (`vonto`) entwickelt, das eine
Selbstauskunft in zwei unabhängige Bestandteile zerlegt: eine
**Beobachtungsmethode**, die festlegt, was vom Modell erfragt wird, und eine
**Referenzgröße**, die festlegt, woran diese Auskunft gemessen wird. Sechs
Selbstauskunftskonstrukte und vier Datensätze werden in dieser Zerlegung
untersucht. Die Reproduktion bestätigt den zentralen Befund des Papers für
Steering, Noising, Probing, Varianzzerlegung und Attention-Blocking; Patching
und Swap replizieren im reduzierten Maßstab nur teilweise. Die Erweiterung
zeigt, dass alle sechs Konstrukte mit ihren berechneten Gegenstücken
korrelieren, aber nicht überwiegend mit dem jeweils theoretisch zugeordneten;
kausal ließ sich in diesem Maßstab nur an der Verbalisierungsposition ein
Effekt nachweisen, nicht an der Zwischenspeicherposition. Die ontologische
Auswertung fällt entsprechend zurückhaltend aus: das Befundmuster ist eher mit
einer Architektur aus Zwischenspeicherung und Abruf vereinbar als mit einer
naiven introspektiven Selbstauskunft, entscheidet die Frage nach dem
ontologischen Status eines LLM-"Glaubens" aber nicht.

## Abstract

Large language models produce self-reports about their own epistemic state on
demand, most commonly as a verbalized confidence rating. Kumaran et al. (2026)
show that this rating is not computed at verbalization time: the relevant
information is formed during answer generation, cached at the token position
immediately after the answer, and retrieved later. This thesis reproduces that
finding independently and at reduced scale on Qwen2.5-7B-Instruct, and then
extends it beyond confidence. The extension introduces a new package (`vonto`)
that decomposes a self-report into two independent parts: an **observation
method**, which fixes what is elicited from the model, and a **ground truth**,
which fixes what that report is checked against. Six self-report constructs
and four datasets are studied in this decomposition. The reproduction confirms
the paper's central claim for steering, noising, probing, variance
partitioning and attention blocking; patching and swap replicate only
partially at reduced scale. The extension finds that all six constructs
correlate with computed counterparts, but not predominantly with the
counterpart each was theoretically paired with, and that at this scale a
causal steering effect was recoverable only at the verbalization position, not
at the caching position. The ontological reading is correspondingly bounded:
the pattern is more consistent with an information-caching and retrieval
architecture than with naive introspective self-report, but it does not settle
what kind of entity an LLM "belief" is.

---

## Erklärung zur Abschlussarbeit

Hiermit erkläre ich, Qi, dass ich die vorliegende Arbeit selbstständig und
ohne Benutzung anderer als der angegebenen Quellen und Hilfsmittel verfasst
habe. Ich bestätige weiterhin, dass die vorliegende Arbeit noch nicht, auch
nicht auszugsweise, für eine andere Prüfungs- oder Studienleistung verwendet
wurde. Ich versichere außerdem, dass alle eingereichten gebundenen schriftlichen
Exemplare meiner Abschlussarbeit mit der digital eingereichten elektronischen
Fassung übereinstimmen.

Frankfurt am Main, den 31.08.2026

_________________________
(Unterschrift)

> **Note for the bound copies.** This declaration must be signed by hand in
> each of the three bound copies, and one additional signed original must be
> handed in as a separate loose sheet (PO 2019 §35 Abs. 16; Merkblatt zur
> Durchführung der Bachelorarbeit, p. 2). The declared "Hilfsmittel" include
> the AI tooling described in the next section.

---

## Note on the Use of AI Tools

This section is not required by any Prüfungsordnung or Prüfungsamt document I
could find, but the declaration above commits me to naming every aid I used,
and AI tooling is such an aid. I therefore state its scope concretely rather
than with a generic disclaimer.

What was AI-assisted. The implementation was written with Claude, driven
through a pipeline of my own called `fatass`, which runs the Claude CLI as an
agent scoped to one directory at a time. That covers the reproduction package
(`vconf`), the extension package (`vonto`), the experiment notebooks, the unit
test suite, and the plotting code, as well as the environment setup scripts.
Brainstorming and planning sessions, including the chapter outline this thesis
follows, were also conducted with the same tooling. Some drafting of this
document was likewise AI-assisted.

What was not. The research questions in Chapter 4 are mine. The decision to
extend the paper by generalizing the self-report construct rather than by
adding models or datasets is mine, as is the observation-method / ground-truth
decomposition that Chapter 6 develops. The interpretation of the results in
Chapters 7 and 8, the choice of which findings count as negative results worth
keeping, and the philosophical argument and its deliberate limits are my own.
Where I judged a result too weak to support a claim, that judgment is mine and
not an artifact of the tooling.

Evidence. Every agent invocation in this project is logged with its full
prompt, working directory, and exit code in the project's `./log` file, and the
git history records every resulting change. Both are available on request.
