# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

#' @keywords internal
.render_framed <- function(plot, params) {
  tmp_in <- tempfile(fileext = ".png")
  on.exit(unlink(tmp_in), add = TRUE)

  dpi <- params$dpi %||% 300L
  title <- params$title %||% ""
  subtitle <- params$subtitle %||% ""
  footnotes <- params$footnotes %||% ""
  sources <- params$sources %||% ""

  figsize <- params$figsize
  if (!is.null(figsize)) {
    if (is.character(figsize)) figsize <- figsizes[[figsize]]
    target_w <- figsize[1]
    target_h <- figsize[2]

    # Round trip 1: ask Python how much plot area is available
    plot_area <- .query_plot_area(
      target_w, target_h,
      title = title, subtitle = subtitle,
      footnotes = footnotes, sources = sources,
      dpi = dpi, python = params$python
    )
    width <- plot_area[["width"]]
    height <- plot_area[["height"]]
  } else {
    target_w <- NULL
    target_h <- NULL
    dev_size <- grDevices::dev.size("in")
    if (dev_size[1] > 1 && dev_size[2] > 1) {
      width <- dev_size[1]
      height <- dev_size[2]
    } else {
      width <- 8
      height <- 5
    }
  }

  # Render ggplot at the exact plot area size
  ggplot2::ggsave(tmp_in, plot = plot, width = width, height = height,
                  dpi = dpi, device = "png")

  png_bytes <- readBin(tmp_in, "raw", file.info(tmp_in)$size)

  # Round trip 2: apply the frame (with target figsize if set)
  framed <- .apply_frame(
    png_bytes,
    title = title, subtitle = subtitle,
    footnotes = footnotes, sources = sources,
    dpi = dpi, python = params$python,
    target_width = target_w, target_height = target_h
  )

  tmp_out <- tempfile(fileext = ".png")
  writeBin(framed, tmp_out)

  if (requireNamespace("png", quietly = TRUE)) {
    img <- png::readPNG(tmp_out)
    grid::grid.newpage()
    grid::grid.raster(img)
  } else {
    # Fallback: base64-encode and display in RStudio Viewer
    tmp_b64 <- tempfile(fileext = ".b64")
    on.exit(unlink(tmp_b64), add = TRUE)
    system2("base64", c("-i", shQuote(tmp_out), "-o", shQuote(tmp_b64)))
    b64 <- paste(readLines(tmp_b64, warn = FALSE), collapse = "")

    tmp_html <- tempfile(fileext = ".html")
    writeLines(sprintf(
      '<html><body style="margin:0;background:#fff"><img src="data:image/png;base64,%s" style="max-width:100%%"></body></html>',
      b64
    ), tmp_html)
    viewer <- getOption("viewer", utils::browseURL)
    viewer(tmp_html)
  }
}


#' Add a corporate frame to a ggplot
#'
#' Add with \code{+} to any ggplot. The frame is applied at print time,
#' so position in the pipeline doesn't matter. Works with \code{print()},
#' \code{ggsave()}, and RStudio display.
#'
#' Title and subtitle are taken from \code{labs()} by default. If set in
#' both \code{labs()} and \code{corporate_frame()}, both render (with a
#' warning).
#'
#' @section Python configuration:
#' The frame is rendered by a Python subprocess. Python is found in this
#' order:
#' \enumerate{
#'   \item \code{python} argument
#'   \item \code{options(corpframe.python = "/path/to/python")}
#'   \item \code{CORPFRAME_PYTHON} environment variable
#'   \item reticulate's Python (if installed)
#'   \item Common system paths
#' }
#'
#' @param title Header title (NULL = use \code{labs(title)}).
#' @param subtitle Header subtitle (NULL = use \code{labs(subtitle)}).
#' @param footnotes Footer text, left-aligned.
#' @param sources Footer text, right-aligned.
#' @param figsize Target layout size. Either a name from \code{\link{figsizes}}
#'   (e.g. \code{"publication_half"}) or a \code{c(width, height)} vector in
#'   inches. If NULL, uses the device dimensions (e.g. from \code{ggsave} or
#'   the RStudio pane).
#' @param dpi Resolution in DPI (default 300).
#' @param python Path to Python (NULL for auto-detect).
#' @return Object to add to a ggplot with \code{+}.
#'
#' @examples
#' \dontrun{
#' library(ggplot2)
#'
#' # Title from labs():
#' ggplot(mtcars, aes(wt, mpg)) + geom_point() +
#'   labs(title = "Weight vs MPG") +
#'   corporate_frame()
#'
#' # Named figsize for a specific layout:
#' ggplot(mtcars, aes(wt, mpg)) + geom_point() +
#'   corporate_frame(title = "Weight vs MPG",
#'                   figsize = "publication_half")
#'
#' # ggsave dimensions are respected when figsize is not set:
#' p <- ggplot(mtcars, aes(wt, mpg)) + geom_point() +
#'   corporate_frame(title = "Weight vs MPG")
#' ggsave("chart.png", p, width = 10, height = 6)
#' }
#' @export
corporate_frame <- function(title = NULL,
                            subtitle = NULL,
                            footnotes = "",
                            sources = "",
                            figsize = NULL,
                            dpi = 300L,
                            python = NULL) {
  if (is.character(figsize) && !figsize %in% names(figsizes)) {
    stop("Unknown figsize '", figsize, "'. See names(figsizes) for options.")
  }
  structure(
    list(title = title, subtitle = subtitle, footnotes = footnotes,
         sources = sources, figsize = figsize, dpi = dpi, python = python),
    class = "corporate_frame_params"
  )
}


#' @export
ggplot_add.corporate_frame_params <- function(object, plot, object_name) {
  attr(plot, "corporate_frame") <- object
  class(plot) <- c("corporate_framed_gg", class(plot))
  # S7 revalidation so RStudio's Environment pane recognizes the object
  # (see _notes.md for details)
  S7::validate(plot)
  plot
}


#' @export
print.corporate_framed_gg <- function(x, ...) {
  params <- attr(x, "corporate_frame")

  class(x) <- setdiff(class(x), "corporate_framed_gg")
  attr(x, "corporate_frame") <- NULL

  if (is.null(params$title)) {
    params$title <- x$labels$title %||% ""
    x$labels$title <- NULL
  } else if (!is.null(x$labels$title)) {
    warning("Both labs(title) and corporate_frame(title) are set; ",
            "both will be rendered.", call. = FALSE)
  }
  if (is.null(params$subtitle)) {
    params$subtitle <- x$labels$subtitle %||% ""
    x$labels$subtitle <- NULL
  } else if (!is.null(x$labels$subtitle)) {
    warning("Both labs(subtitle) and corporate_frame(subtitle) are set; ",
            "both will be rendered.", call. = FALSE)
  }

  .render_framed(x, params)

  invisible(x)
}
