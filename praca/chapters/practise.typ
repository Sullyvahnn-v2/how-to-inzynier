= Wstęp i cel pracy <ch-wstep>

W niniejszym rozdziale przedstawiono wprowadzenie do problematyki projektu oraz cele pracy inżynierskiej. System został zaprojektowany zgodnie z wymogami opisanymi w sekcji @sec-wymagania.

== Kontekst i motywacja

Projektowanie nowoczesnych aplikacji wymaga uwzględnienia wydajności oraz łatwości utrzymania kodu. Główne czynniki wpływające na sukces przedsięwzięcia to:

- Optymalizacja czasu odpowiedzi serwera.
- Skalowalność architektury microservices.
- Bezpieczeństwo danych użytkowników #footnote[Zgodnie z dyrektywami RODO/GDPR].

== Wymagania systemowe <sec-wymagania>

Wymagania zostały podzielone na funkcjonalne oraz niefunkcjonalne. Szacunkowe zapotrzebowanie na zasoby opisuje wzór @eq-wydajnosc:

$P_x = sum_(i=1)^n (C_i * M_i)$ <eq-wydajnosc>

Gdzie $C_i$ oznacza obciążenie CPU, a $M_i$ zużycie pamięci dla danego modułu.

=== Zestawienie modułów

W poniższej tabeli (@tbl-moduly) przedstawiono kluczowe elementy składowe.

#figure(
  table(
    columns: (1fr, 2fr, 1fr),
    align: (left, left, center),
    [*Nazwa modułu*], [*Opis funkcji*], [*Status*],
    [API Gateway], [Ruch wejściowy i autoryzacja], [Ukończony],
    [Core Engine], [Przetwarzanie danych w czasie rzeczywistym], [W trakcie],
    [Database], [Przechowywanie danych relacyjnych], [Ukończony],
  ),
  caption: [Zestawienie modułów systemowych],
) <tbl-moduly>

== Architektura rozwiązania

Schemat blokowy proponowanej architektury przedstawiono poniżej.

---

#v(1cm)
*Uwagi dotyczące składni Typst w tym pliku:*
- `= Nazwa` – nagłówek rozdziału (stopień 1).
- `== Nazwa` / `=== Nazwa` – podrodziały (stopnie 2 i 3).
- `<etykieta>` – etykieta służąca do odwołań (używasz `@etykieta` w tekście).
- `#figure(...)` – kontener na tabele i obrazy zapewniający automatyczne numerowanie i podpisy.
