#let project(
  title: "",
  title_translated: none,
  author: str,
  supervisor: none,
  assistant_supervisor: none,
  date: none,
  body,
) = {
  set document(author: author, title: title)

  let line-indent = 1.5em
  let lines-spacing = 0.65em

  set math.equation(numbering: "1")
  set page(margin: auto)
  set heading(numbering: "1.")
  set par(leading: 0.55em, first-line-indent: 1.8em, justify: true)
  set text(font: "New Computer Modern", lang: "en", size: 11pt)
  show raw: set text(font: "Times New Roman")

  set par(first-line-indent: line-indent, justify: true, leading: lines-spacing)
  set par(spacing: lines-spacing)
  show link: underline

  show heading: set block(above: 1.4em, below: 1em)
  show heading: it => {
    v(0.5em)
    it
    v(0.5em)
    par()[#text(size: 0.5em)[#h(0.0em)]]
  }

  show heading.where(level: 4): it => {
    v(0.5em)
    block(it.body)
    v(0.1em)
    par()[#text(size: 0.5em)[#h(0.0em)]]
  }

  show figure: fig => {
    v(1.0em)
    fig
    par()[#text(size: 0.0em)[#h(0.0em)]]
  }

  let text_strong(content) = text(weight: 700, 1.2em)[#content]
  let text_normal(content) = text(1.1em)[#content]
  let table_text(content) = text(1em)[#content]
  let table_entry(content) = text(1.1em, weight: 600)[#content]

  set text(hyphenate: false)
  set par(justify: false)

  align(center)[
    #v(1em)
    #image("images/AGH.jpg", height: 140pt)
    #v(2em)
    #text_strong("AGH University of Krakow")
    #linebreak()
    #v(1em)
    #text("Faculty of Computer Science", size: 1.2em)
    #v(3em)
    #text("Engineering Thesis", size: 1.5em)
    #v(3em)
    #text(title, size: 1.8em, weight: 600)
    #if title_translated != none [
      #linebreak()
      #v(0.5em)
      #text(title_translated, size: 1.1em, weight: 500)
    ]
    #v(6em)
    #align(left)[
      #pad(left: 1.5em, table(
        columns: (16em, auto),
        row-gutter: 0.3em,
        stroke: none,
        table_text("Author:"), table_entry(author),
        table_text("Field of study:"), table_entry("Computer Science"),
        table_text("Supervisor:"), table_entry(supervisor),
      ))
    ]
  ]

  set text(hyphenate: auto)
  set par(justify: true)

  align(center + bottom)[
    #text_normal()[#{
      (
        [Kraków]
          + [,#if date != none [
              #date.year()
            ]]
      )
    }]
  ]

  show table: set par(justify: false)
  body
}
