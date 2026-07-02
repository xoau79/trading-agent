---
title: Introduction to R and RStudio
source: https://www.interactivebrokers.com/campus/trading-lessons/introduction-to-r-and-rstudio/
type: reference
course: trading-using-r
date_added: 2026-06-13
tags: [ibkr-api, r-language, rstudio, ibrokers-package, algorithmic-trading]
---

# Introduction to R and RStudio

## Concepts

- Orientation lesson for the **Trading Using R** course (intermediate level, contributed by **QuantInsti**). The course teaches automated trading and backtesting against IBKR using the **IBrokers** R package - a pure-R implementation of the TWS API created by Jeffrey Ryan and now maintained by Joshua Ulrich. See [[introduction-to-ibrokers-package]].
- **R** is a free, open-source language and environment for scientific/statistical computing and graphics. It grew out of the S language (Bell Labs, 1970s) and was created in the early 1990s by Ross Ihaka and Robert Gentleman. "R" names both the language and the software.
- Why R suits automated trading: free/open-source, thousands of contributed CRAN packages, the ability to write your own packages, and specialized quant packages - **Quantstrat**, **QuantTools**, **PerformanceAnalytics** - for backtesting and performance analytics. Lets you prototype a strategy quickly and compare backtested vs. real-world results with minimal code changes.
- **RStudio** is an IDE (integrated development environment) for R - one tool for editing source, running/building code, and debugging. Other IDEs exist (Visual Studio, Eclipse) but the lesson considers RStudio the best for R.
- **Key dependency:** R can run on its own; RStudio cannot run without R installed. RStudio auto-detects the installed R version when it is set up, so install order matters - see [[installing-r-and-rstudio]].

## Code examples

None - this lesson is orientation only.

## Gotchas

- This course's later lessons present their R code as **screenshots/images**, not copy-paste text. These notes therefore capture the concepts and documented function signatures rather than transcribed scripts.
- IBrokers is third-party (Ryan/Ulrich); IBKR makes no representations about its performance or accuracy and provides the material for education only - not investment advice.

## Related

- Next: [[installing-r-and-rstudio]]
- The package this course is built around: [[introduction-to-ibrokers-package]]
- (First lesson of the course.)
