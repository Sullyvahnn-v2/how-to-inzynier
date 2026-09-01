#import "metadata.typ" as metadata

#show: metadata.project.with(
  title: [Designing a Reliable Engineering Thesis Workflow],
  author: "Artur Wojnar",
  title_translated: [A practical template for a modern engineering project],
  supervisor: "dr inż. Paweł Kułakowski",
  date: datetime(year: 2026, month: 9, day: 6),
)

#pagebreak()

#outline(title: "Table of Contents")

#pagebreak()

#include "chapters/practise.typ"

#bibliography("bibliography.bib", title: "References", style: "ieee")
