# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

#' Save a ggplot with corporate frame
#'
#' Renders the ggplot to PNG via \code{ggsave}, then wraps it with the
#' corporate design frame (header with title/subtitle, footer with
#' footnotes/sources) via the Python/matplotlib subprocess.
#'
#' @param plot A ggplot2 object.
#' @param filename Output file path (e.g. \code{"chart.png"}).
#' @param title Header title (bold, with accent underline).
#' @param subtitle Header subtitle (italic, below title).
#' @param footnotes Footer text, left-aligned.
#' @param sources Footer text, right-aligned.
#' @param width Plot width in inches (passed to \code{ggsave}).
#' @param height Plot height in inches (passed to \code{ggsave}).
#' @param dpi Resolution in DPI (used for both ggsave and the frame).
#' @param python Path to Python executable (NULL for auto-detect).
#' @return Invisibly, the output file path.
#'
#' @examples
#' \dontrun{
#' library(ggplot2)
#' p <- ggplot(mtcars, aes(wt, mpg)) + geom_point()
#' ggsave_corporate(p, "cars_corporate.png",
#'   title = "Weight vs MPG",
#'   subtitle = "mtcars dataset"
#' )
#' }
#' @export
ggsave_corporate <- function(plot,
                              filename,
                              title = "",
                              subtitle = "",
                              footnotes = "",
                              sources = "",
                              width = 8,
                              height = 5,
                              dpi = 300L,
                              python = NULL) {
  framed <- ggsave_corporate_bytes(
    plot,
    title = title,
    subtitle = subtitle,
    footnotes = footnotes,
    sources = sources,
    width = width,
    height = height,
    dpi = dpi,
    python = python
  )

  writeBin(framed, filename)
  invisible(filename)
}


#' Render a ggplot with corporate frame as raw bytes
#'
#' Same as \code{\link{ggsave_corporate}} but returns the framed PNG as a
#' raw vector instead of writing to a file. Useful for embedding in Shiny,
#' RMarkdown, or sending to an API.
#'
#' @inheritParams ggsave_corporate
#' @return Raw vector of the framed PNG image.
#'
#' @examples
#' \dontrun{
#' library(ggplot2)
#' p <- ggplot(mtcars, aes(wt, mpg)) + geom_point()
#' bytes <- ggsave_corporate_bytes(p,
#'   title = "Weight vs MPG",
#'   subtitle = "mtcars dataset"
#' )
#' writeBin(bytes, "chart.png")
#' }
#' @export
ggsave_corporate_bytes <- function(plot,
                                    title = "",
                                    subtitle = "",
                                    footnotes = "",
                                    sources = "",
                                    width = 8,
                                    height = 5,
                                    dpi = 300L,
                                    python = NULL) {
  # Render ggplot to temp PNG
  tmp <- tempfile(fileext = ".png")
  on.exit(unlink(tmp), add = TRUE)

  ggplot2::ggsave(tmp, plot = plot, width = width, height = height,
                  dpi = dpi, device = "png")

  png_bytes <- readBin(tmp, "raw", file.info(tmp)$size)

  # Apply corporate frame
  apply_frame(
    png_bytes,
    title = title,
    subtitle = subtitle,
    footnotes = footnotes,
    sources = sources,
    dpi = dpi,
    python = python
  )
}
