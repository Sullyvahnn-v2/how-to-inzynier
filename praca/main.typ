#import "metadata.typ" as metadata

#show: metadata.project.with(
  title: [Symulator Radaru SAR],
  author: "Artur Wojnar",
  supervisor: "dr inż. Paweł Kułakowski",
  date: datetime(year: 2026, month: 9, day: 6),
)

#pagebreak()

#outline(title: "Spis treści")

#pagebreak()

#include "chapters/theory.typ"

#pagebreak()

#include "chapters/practise.typ"


#bibliography("bibliography.bib", title: "Bibliografia", style: "ieee")
