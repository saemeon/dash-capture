# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

#' @keywords internal
.query_plot_area <- function(width, height,
                             title = "", subtitle = "",
                             footnotes = "", sources = "",
                             dpi = 300L, python = NULL) {
  python <- .find_python(python)

  cmd <- paste(
    shQuote(python), "-m", "corpframe",
    "--query-plot-area",
    "--target-width", as.character(width),
    "--target-height", as.character(height),
    "--title", shQuote(title),
    "--subtitle", shQuote(subtitle),
    "--footnotes", shQuote(footnotes),
    "--sources", shQuote(sources),
    "--dpi", as.character(dpi)
  )

  result <- system(cmd, intern = TRUE)
  status <- attr(result, "status")

  if (!is.null(status) && status != 0) {
    stop("query_plot_area failed (exit ", status, "):\n",
         paste(result, collapse = "\n"))
  }

  parsed <- jsonlite::fromJSON(result)
  c(width = parsed$width, height = parsed$height)
}


#' @keywords internal
.apply_frame <- function(png_bytes,
                         title = "",
                         subtitle = "",
                         footnotes = "",
                         sources = "",
                         dpi = 300L,
                         python = NULL,
                         target_width = NULL,
                         target_height = NULL) {
  python <- .find_python(python)

  input_file <- tempfile(fileext = ".png")
  output_file <- tempfile(fileext = ".png")
  on.exit(unlink(c(input_file, output_file)), add = TRUE)

  writeBin(png_bytes, input_file)

  cmd <- paste(
    shQuote(python), "-m", "corpframe",
    "--input", shQuote(input_file),
    "--output", shQuote(output_file),
    "--title", shQuote(title),
    "--subtitle", shQuote(subtitle),
    "--footnotes", shQuote(footnotes),
    "--sources", shQuote(sources),
    "--dpi", as.character(dpi)
  )

  if (!is.null(target_width) && !is.null(target_height)) {
    cmd <- paste(cmd,
      "--target-width", as.character(target_width),
      "--target-height", as.character(target_height)
    )
  }

  result <- system(cmd, intern = TRUE)
  status <- attr(result, "status")

  if (!is.null(status) && status != 0) {
    stop(
      "Corporate frame Python script failed (exit ", status, "):\n",
      paste(result, collapse = "\n")
    )
  }

  if (!file.exists(output_file)) {
    stop("Corporate frame output file not created. Python output:\n",
         paste(result, collapse = "\n"))
  }

  readBin(output_file, "raw", file.info(output_file)$size)
}
